from __future__ import annotations

import io
import wave


class AudioFormatError(ValueError):
    """Raised when audio is not the format required by the ASR boundary."""


SAMPLE_RATE_HZ = 16_000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2


def pcm16_to_wav(
    pcm: bytes,
    *,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
    channels: int = CHANNELS,
) -> bytes:
    if not pcm:
        raise AudioFormatError("audio segment is empty")
    if sample_rate_hz <= 0 or channels != CHANNELS:
        raise AudioFormatError("only positive 16 kHz mono audio is supported")
    if len(pcm) % SAMPLE_WIDTH_BYTES:
        raise AudioFormatError("PCM16 data must contain complete samples")

    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(sample_rate_hz)
        wav_file.writeframes(pcm)
    return output.getvalue()


def validate_wav(
    audio: bytes,
    *,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
    channels: int = CHANNELS,
) -> None:
    if not audio:
        raise AudioFormatError("WAV data is empty")
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav_file:
            if wav_file.getnchannels() != channels:
                raise AudioFormatError("WAV must be mono")
            if wav_file.getsampwidth() != SAMPLE_WIDTH_BYTES:
                raise AudioFormatError("WAV must use PCM16 samples")
            if wav_file.getframerate() != sample_rate_hz:
                raise AudioFormatError("WAV must use a 16 kHz sample rate")
            if wav_file.getnframes() == 0:
                raise AudioFormatError("WAV contains no audio frames")
    except (wave.Error, EOFError) as exc:
        raise AudioFormatError("invalid WAV data") from exc
