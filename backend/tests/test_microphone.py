import threading
from types import SimpleNamespace

import numpy as np

from app.services import microphone


def test_list_input_devices_uses_only_devices_with_input_channels(monkeypatch) -> None:
    fake_sounddevice = SimpleNamespace(
        query_devices=lambda: [
            {"name": "Output only", "max_input_channels": 0},
            {"name": "Desk microphone", "max_input_channels": 2},
        ]
    )
    monkeypatch.setattr(microphone, "_sounddevice", lambda: fake_sounddevice)

    assert microphone.list_input_devices() == [(1, "Desk microphone", 2)]


def test_microphone_config_calculates_20ms_blocksize() -> None:
    config = microphone.MicrophoneConfig()

    assert config.blocksize == 320


def test_microphone_capture_yields_mocked_pcm_frame(monkeypatch) -> None:
    class FakeInputStream:
        def __init__(self, *, callback, **kwargs) -> None:
            del kwargs
            self.callback = callback

        def __enter__(self):
            self.callback(np.zeros((320, 1), dtype=np.int16), 320, None, None)
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            del exc_type, exc_value, traceback

    fake_sounddevice = SimpleNamespace(InputStream=FakeInputStream)
    monkeypatch.setattr(microphone, "_sounddevice", lambda: fake_sounddevice)
    stop_event = threading.Event()
    frames = microphone.MicrophoneCapture().frames(stop_event)

    captured = next(frames)
    stop_event.set()

    assert captured == b"\x00\x00" * 320
