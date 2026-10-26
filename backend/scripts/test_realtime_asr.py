"""Hands-free PC microphone test for Typhoon file-based transcription."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from app.audio import pcm16_to_wav
from app.config import get_settings
from app.services.asr import (
    ASRProvider,
    MockASRProvider,
    TyphoonAPIProvider,
    TyphoonSelfHostedProvider,
)
from app.services.microphone import (
    MicrophoneCapture,
    MicrophoneConfig,
    MicrophoneError,
    list_input_devices,
)
from app.services.vad import SpeechSegmenter, VADConfig


def parse_device(value: str) -> int | str:
    return int(value) if value.isdigit() else value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Continuously listen and transcribe speech with Typhoon ASR."
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="list available input devices and exit",
    )
    parser.add_argument(
        "--device",
        type=parse_device,
        help="input device index or name (default: system default)",
    )
    parser.add_argument(
        "--provider",
        choices=("typhoon_api", "mock", "typhoon_self_hosted"),
        default="typhoon_api",
        help="ASR provider (default: typhoon_api)",
    )
    parser.add_argument(
        "--vad-sensitivity",
        type=int,
        choices=range(4),
        metavar="0-3",
        default=2,
        help="WebRTC VAD aggressiveness (0=least, 3=most)",
    )
    parser.add_argument("--pre-roll-ms", type=int, default=300)
    parser.add_argument("--silence-timeout-ms", type=int, default=800)
    parser.add_argument("--min-speech-ms", type=int, default=200)
    parser.add_argument("--max-recording-ms", type=int, default=8_000)
    parser.add_argument(
        "--save-wav",
        type=Path,
        metavar="DIR",
        help="optionally save completed segments as WAV files for debugging",
    )
    return parser


def create_provider(provider_name: str) -> ASRProvider:
    settings = get_settings()
    if provider_name == "mock":
        return MockASRProvider(text="ตัวอย่างข้อความจาก mock provider")
    if provider_name == "typhoon_api":
        return TyphoonAPIProvider(
            api_base_url=settings.typhoon_api_base_url,
            model=settings.typhoon_asr_model,
            api_key=settings.typhoon_api_key,
            timeout_s=settings.typhoon_api_timeout_s,
        )
    return TyphoonSelfHostedProvider(base_url=settings.typhoon_self_host_url)


def transcribe_wav(provider: ASRProvider, wav_audio: bytes):
    return asyncio.run(
        provider.transcribe(
            wav_audio,
            filename="utterance.wav",
            content_type="audio/wav",
        )
    )


def save_wav(directory: Path, wav_audio: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    path = directory / f"utterance_{stamp}.wav"
    path.write_bytes(wav_audio)
    return path


def print_devices() -> None:
    for index, name, channels in list_input_devices():
        print(f"[{index}] {name} (input channels: {channels})")


def run(args: argparse.Namespace) -> int:
    if args.list_devices:
        try:
            print_devices()
        except MicrophoneError as exc:
            print(f"ไม่สามารถอ่านรายการ microphone: {exc}", file=sys.stderr)
            return 1
        return 0

    vad_config = VADConfig(
        pre_roll_ms=args.pre_roll_ms,
        silence_timeout_ms=args.silence_timeout_ms,
        min_speech_ms=args.min_speech_ms,
        max_recording_ms=args.max_recording_ms,
        aggressiveness=args.vad_sensitivity,
    )
    segmenter = SpeechSegmenter(vad_config)
    microphone = MicrophoneCapture(
        MicrophoneConfig(
            frame_duration_ms=vad_config.frame_duration_ms,
            device=args.device,
        )
    )
    provider = create_provider(args.provider)
    pending: list[tuple[Future, float]] = []
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lantern-asr")

    print(
        "Lantern กำลังฟัง microphone แบบ hands-free "
        f"(provider={args.provider}, กด Ctrl+C เพื่อออก)"
    )
    try:
        for pcm_segment in microphone.frames():
            for future, started_at in pending[:]:
                if not future.done():
                    continue
                pending.remove((future, started_at))
                try:
                    transcript = future.result()
                    elapsed = time.perf_counter() - started_at
                    print(f"ภาษาไทย: {transcript.text} | ASR latency: {elapsed:.3f}s")
                except Exception as exc:
                    print(f"ข้อผิดพลาด ASR: {exc}", file=sys.stderr)

            segment = segmenter.process_frame(pcm_segment)
            if segment is None:
                continue
            wav_audio = pcm16_to_wav(segment)
            if args.save_wav:
                print(f"บันทึกไฟล์ debug: {save_wav(args.save_wav, wav_audio)}")
            pending.append(
                (
                    executor.submit(transcribe_wav, provider, wav_audio),
                    time.perf_counter(),
                )
            )
    except KeyboardInterrupt:
        print("\nหยุดการฟังแล้ว")
        return 0
    except MicrophoneError as exc:
        print(f"ข้อผิดพลาด microphone: {exc}", file=sys.stderr)
        return 1
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return 0


def main() -> int:
    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
