from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Protocol


class FrameVAD(Protocol):
    def is_speech(self, frame: bytes, sample_rate_hz: int) -> bool: ...


@dataclass(frozen=True)
class VADConfig:
    """Bounded utterance-capture settings for future ESP32/backend use."""

    sample_rate_hz: int = 16_000
    frame_duration_ms: int = 20
    silence_timeout_ms: int = 800
    min_speech_ms: int = 200
    max_recording_ms: int = 8_000
    pre_roll_ms: int = 300
    aggressiveness: int = 2

    def __post_init__(self) -> None:
        if self.sample_rate_hz != 16_000:
            raise ValueError("Phase 1 VAD requires a 16 kHz sample rate")
        if self.frame_duration_ms not in (10, 20, 30):
            raise ValueError("WebRTC VAD frames must be 10, 20, or 30 ms")
        if not 0 <= self.aggressiveness <= 3:
            raise ValueError("VAD aggressiveness must be between 0 and 3")


class WebRTCVAD:
    def __init__(self, aggressiveness: int = 2) -> None:
        import webrtcvad

        self._vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame: bytes, sample_rate_hz: int) -> bool:
        return self._vad.is_speech(frame, sample_rate_hz)


class SpeechSegmenter:
    """Turn fixed-size PCM16 frames into bounded speech segments."""

    def __init__(
        self,
        config: VADConfig | None = None,
        *,
        detector: FrameVAD | None = None,
    ) -> None:
        self.config = config or VADConfig()
        self._detector = detector or WebRTCVAD(self.config.aggressiveness)
        self._frame_bytes = (
            self.config.sample_rate_hz
            * self.config.frame_duration_ms
            // 1000
            * 2
        )
        pre_roll_frames = max(
            1, (self.config.pre_roll_ms + self.config.frame_duration_ms - 1)
            // self.config.frame_duration_ms
        )
        self._pre_roll = deque(maxlen=pre_roll_frames)
        self._recording: list[bytes] = []
        self._recording_ms = 0
        self._speech_ms = 0
        self._silence_ms = 0

    @property
    def is_recording(self) -> bool:
        return bool(self._recording)

    @property
    def frame_bytes(self) -> int:
        return self._frame_bytes

    def process_frame(self, frame: bytes) -> bytes | None:
        if len(frame) != self._frame_bytes:
            raise ValueError(
                f"expected {self._frame_bytes} PCM bytes, received {len(frame)}"
            )
        speech = self._detector.is_speech(frame, self.config.sample_rate_hz)

        if not self.is_recording:
            self._pre_roll.append(frame)
            if speech:
                self._recording = list(self._pre_roll)
                self._recording_ms = len(self._recording) * self.config.frame_duration_ms
                self._speech_ms = self.config.frame_duration_ms
                self._silence_ms = 0
            return None

        self._recording.append(frame)
        self._recording_ms += self.config.frame_duration_ms
        if speech:
            self._speech_ms += self.config.frame_duration_ms
            self._silence_ms = 0
        else:
            self._silence_ms += self.config.frame_duration_ms

        should_end = (
            self._silence_ms >= self.config.silence_timeout_ms
            or self._recording_ms >= self.config.max_recording_ms
        )
        if should_end:
            return self._finish() if self._speech_ms >= self.config.min_speech_ms else self._discard()
        return None

    def flush(self) -> bytes | None:
        if not self.is_recording:
            return None
        return self._finish() if self._speech_ms >= self.config.min_speech_ms else self._discard()

    def _finish(self) -> bytes:
        segment = b"".join(self._recording)
        self._reset()
        return segment

    def _discard(self) -> None:
        self._reset()
        return None

    def _reset(self) -> None:
        self._recording.clear()
        self._recording_ms = 0
        self._speech_ms = 0
        self._silence_ms = 0
        self._pre_roll.clear()


class VoiceActivityDetector:
    """Compatibility wrapper for callers that need a configured frame VAD."""

    def __init__(self, config: VADConfig | None = None) -> None:
        self.config = config or VADConfig()
        self._detector = WebRTCVAD(self.config.aggressiveness)

    def is_speech(self, pcm_frame: bytes) -> bool:
        return self._detector.is_speech(pcm_frame, self.config.sample_rate_hz)
