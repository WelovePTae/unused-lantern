from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Iterator

import numpy as np


class MicrophoneError(RuntimeError):
    """Raised when the local microphone cannot be opened or read."""


@dataclass(frozen=True)
class MicrophoneConfig:
    sample_rate_hz: int = 16_000
    channels: int = 1
    frame_duration_ms: int = 20
    device: int | str | None = None

    @property
    def blocksize(self) -> int:
        return self.sample_rate_hz * self.frame_duration_ms // 1000


def _sounddevice():
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise MicrophoneError(
            "sounddevice is not installed; run `uv sync --dev`"
        ) from exc
    return sd


def list_input_devices() -> list[tuple[int, str, int]]:
    sd = _sounddevice()
    try:
        devices = sd.query_devices()
    except Exception as exc:
        raise MicrophoneError("could not enumerate audio devices") from exc
    return [
        (index, str(device["name"]), int(device.get("max_input_channels", 0)))
        for index, device in enumerate(devices)
        if int(device.get("max_input_channels", 0)) > 0
    ]


class MicrophoneCapture:
    """Non-blocking callback capture yielding fixed-size PCM16 frames."""

    def __init__(self, config: MicrophoneConfig | None = None) -> None:
        self.config = config or MicrophoneConfig()

    def frames(self, stop_event: threading.Event | None = None) -> Iterator[bytes]:
        sd = _sounddevice()
        pending: queue.Queue[bytes] = queue.Queue(maxsize=32)
        errors: queue.Queue[str] = queue.Queue(maxsize=1)

        def callback(indata, frames, time_info, status) -> None:
            del frames, time_info
            if status:
                # The CLI reports stream errors when the stream itself fails.
                pass
            pcm = np.asarray(indata, dtype=np.int16).reshape(-1).tobytes()
            try:
                pending.put_nowait(pcm)
            except queue.Full:
                try:
                    errors.put_nowait("capture queue overflow")
                except queue.Full:
                    pass

        try:
            with sd.InputStream(
                samplerate=self.config.sample_rate_hz,
                blocksize=self.config.blocksize,
                channels=self.config.channels,
                dtype="int16",
                device=self.config.device,
                callback=callback,
            ):
                while stop_event is None or not stop_event.is_set():
                    if not errors.empty():
                        raise MicrophoneError(errors.get_nowait())
                    try:
                        yield pending.get(timeout=0.5)
                    except queue.Empty:
                        continue
        except KeyboardInterrupt:
            return
        except MicrophoneError:
            raise
        except Exception as exc:
            raise MicrophoneError("microphone stream stopped unexpectedly") from exc
