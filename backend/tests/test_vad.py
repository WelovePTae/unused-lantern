from collections.abc import Iterable

import pytest

from app.services.vad import SpeechSegmenter, VADConfig


class FakeVAD:
    def __init__(self, decisions: Iterable[bool]) -> None:
        self.decisions = iter(decisions)

    def is_speech(self, frame: bytes, sample_rate_hz: int) -> bool:
        del frame, sample_rate_hz
        return next(self.decisions)


def frame(byte: int = 1) -> bytes:
    return bytes([byte]) * 640  # 20 ms at 16 kHz, PCM16


def test_speech_starts_after_voice_and_ends_after_silence() -> None:
    segmenter = SpeechSegmenter(
        VADConfig(pre_roll_ms=300, silence_timeout_ms=40, min_speech_ms=40),
        detector=FakeVAD([False, True, True, False, False]),
    )

    assert segmenter.process_frame(frame(0)) is None
    assert segmenter.is_recording is False
    assert segmenter.process_frame(frame(2)) is None
    assert segmenter.is_recording is True
    assert segmenter.process_frame(frame(3)) is None
    assert segmenter.process_frame(frame(0)) is None
    segment = segmenter.process_frame(frame(0))

    assert segment is not None
    assert len(segment) == 5 * 640
    assert segmenter.is_recording is False


def test_short_noise_is_discarded_after_silence() -> None:
    segmenter = SpeechSegmenter(
        VADConfig(silence_timeout_ms=40, min_speech_ms=60),
        detector=FakeVAD([True, False, False]),
    )

    assert segmenter.process_frame(frame()) is None
    assert segmenter.process_frame(frame(0)) is None
    assert segmenter.process_frame(frame(0)) is None
    assert segmenter.is_recording is False


def test_frame_size_is_validated() -> None:
    segmenter = SpeechSegmenter(detector=FakeVAD([]))

    with pytest.raises(ValueError):
        segmenter.process_frame(b"short")
