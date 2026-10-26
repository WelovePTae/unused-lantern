"""Measure the local FastAPI command pipeline without a paid ASR request.

This benchmark uses mocked ASR responses. It measures backend request latency,
not microphone capture, Wi-Fi, Typhoon, or physical relay switching latency.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import statistics
import time
from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.audio import pcm16_to_wav
from app.config import Settings
from app.main import create_app
from app.services.asr import MockASRProvider
from app.schemas import Transcript


class ErrorASRProvider:
    name = "mock-error"

    async def transcribe(
        self, audio: bytes, *, filename: str, content_type: str
    ) -> Transcript:
        raise RuntimeError("simulated ASR failure")


@dataclass(frozen=True)
class Case:
    name: str
    transcript: str
    expect_status: int
    expect_accepted: bool | None
    asr_error: bool = False


CASES = (
    Case("LIGHT_ON", "\u0e15\u0e35\u0e4b \u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f", 200, True),
    Case("LIGHT_OFF", "\u0e15\u0e35\u0e4b \u0e1b\u0e34\u0e14\u0e44\u0e1f", 200, True),
    Case("MISSING_WAKE_WORD", "\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f", 200, False),
    Case("INVALID_COMMAND", "\u0e15\u0e35\u0e4b \u0e27\u0e31\u0e19\u0e19\u0e35\u0e49\u0e2d\u0e32\u0e01\u0e32\u0e28\u0e14\u0e35", 200, False),
    Case("NO_SPEECH", "", 200, False),
    Case("BACKEND_ERROR", "", 503, None, asr_error=True),
)


def wav_fixture(seed: int) -> bytes:
    return pcm16_to_wav((b"\x00\x00" * 160) + bytes([seed & 0xFF, 0]))


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def run_case(case: Case, iterations: int) -> list[float]:
    latencies: list[float] = []
    for iteration in range(iterations):
        application = create_app(
            Settings(
                require_wake_word=True,
                wake_phrase="\u0e15\u0e35\u0e4b",
                wake_word_alternatives="tee,\u0e15\u0e35,\u0e17\u0e35",
            )
        )
        application.state.asr_provider = (
            ErrorASRProvider()
            if case.asr_error
            else MockASRProvider(case.transcript)
        )
        client = TestClient(application)
        started = time.perf_counter()
        response = client.post(
            "/v1/utterances/transcribe",
            files={"audio": (f"benchmark-{iteration}.wav", wav_fixture(iteration), "audio/wav")},
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies.append(elapsed_ms)

        if response.status_code != case.expect_status:
            raise AssertionError(
                f"{case.name}: expected HTTP {case.expect_status}, got {response.status_code}"
            )
        if case.expect_accepted is not None:
            actual = response.json()["intent"]["accepted"]
            if actual != case.expect_accepted:
                raise AssertionError(
                    f"{case.name}: expected accepted={case.expect_accepted}, got {actual}"
                )
    return latencies


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=5, help="requests per case")
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")

    print("case,iterations,avg_ms,median_ms,p95_ms,min_ms,max_ms")
    all_latencies: list[float] = []
    for case in CASES:
        latencies = run_case(case, args.iterations)
        all_latencies.extend(latencies)
        print(
            f"{case.name},{len(latencies)},{statistics.mean(latencies):.2f},"
            f"{statistics.median(latencies):.2f},{percentile(latencies, 0.95):.2f},"
            f"{min(latencies):.2f},{max(latencies):.2f}"
        )
    print(
        f"TOTAL,{len(all_latencies)},{statistics.mean(all_latencies):.2f},"
        f"{statistics.median(all_latencies):.2f},{percentile(all_latencies, 0.95):.2f},"
        f"{min(all_latencies):.2f},{max(all_latencies):.2f}"
    )


if __name__ == "__main__":
    main()
