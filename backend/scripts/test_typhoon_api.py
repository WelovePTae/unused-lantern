from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from app.audio import AudioFormatError, validate_wav
from app.config import get_settings
from app.services.asr import TyphoonAPIProvider
from app.services.intents import IntentDetector
from app.services.wake_word import WakeWordVerifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one controlled Typhoon ASR request and the Phase 3 pipeline."
    )
    parser.add_argument(
        "--wav",
        type=Path,
        help="16-kHz mono PCM16 WAV file for the live request",
    )
    parser.add_argument(
        "--test-invalid-audio",
        action="store_true",
        help="verify local invalid-WAV rejection without calling Typhoon",
    )
    return parser.parse_args()


async def run_live_request(audio_path: Path) -> int:
    settings = get_settings()
    if not settings.typhoon_api_key:
        print("BLOCKED: TYPHOON_API_KEY is not configured; no live request sent.")
        return 2

    audio = audio_path.read_bytes()
    validate_wav(audio)
    provider = TyphoonAPIProvider(
        api_base_url=settings.typhoon_api_base_url,
        model=settings.typhoon_asr_model,
        api_key=settings.typhoon_api_key,
        timeout_s=settings.typhoon_api_timeout_s,
    )
    started = time.perf_counter()
    try:
        transcript = await provider.transcribe(
            audio,
            filename=audio_path.name,
            content_type="audio/wav",
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        print(
            "FAIL: Typhoon request error "
            f"after {elapsed_ms:.1f} ms ({type(exc).__name__})"
        )
        return 1

    elapsed_ms = (time.perf_counter() - started) * 1000
    wake_match = WakeWordVerifier(
        settings.wake_phrase,
        tuple(part.strip() for part in settings.wake_word_alternatives.split(",")),
    ).match(transcript.text)
    intent = (
        IntentDetector().detect(wake_match.command_text)
        if wake_match.detected
        else {"name": "IGNORE", "accepted": False, "reason": "wake word missing"}
    )
    print("PASS: live Typhoon request completed")
    print(f"endpoint={settings.typhoon_api_base_url} model={settings.typhoon_asr_model}")
    print(f"latency_ms={elapsed_ms:.1f}")
    print(f"transcript={transcript.text!r}")
    print(
        json.dumps(
            {
                "wake_word_detected": wake_match.detected,
                "matched_wake_word": wake_match.matched_phrase,
                "intent": intent.model_dump() if hasattr(intent, "model_dump") else intent,
            },
            ensure_ascii=False,
        )
    )
    return 0


async def main() -> int:
    args = parse_args()
    if args.test_invalid_audio:
        try:
            validate_wav(b"RIFF-invalid-WAVE")
        except AudioFormatError:
            print("PASS: invalid WAV rejected locally; no Typhoon request sent")
        else:
            print("FAIL: invalid WAV was accepted")
            return 1

    if args.wav is None:
        if args.test_invalid_audio:
            return 0
        print("NOT RUN: provide --wav for the controlled live request")
        return 3
    if not args.wav.is_file():
        print(f"FAIL: WAV file not found: {args.wav}")
        return 1
    try:
        return await run_live_request(args.wav)
    except (AudioFormatError, OSError) as exc:
        print(f"FAIL: input WAV error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
