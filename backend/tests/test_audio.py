import pytest

from app.audio import AudioFormatError, pcm16_to_wav, validate_wav


def test_pcm16_to_wav_creates_valid_16khz_mono_audio() -> None:
    audio = pcm16_to_wav(b"\x00\x00" * 320)

    validate_wav(audio)


def test_invalid_wav_is_rejected() -> None:
    with pytest.raises(AudioFormatError):
        validate_wav(b"not a wav")


def test_empty_pcm_is_rejected() -> None:
    with pytest.raises(AudioFormatError):
        pcm16_to_wav(b"")
