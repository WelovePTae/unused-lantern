from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def save_wav(audio: bytes, directory: str) -> Path:
    """Save one already-validated WAV payload as a uniquely named debug file."""
    target_directory = Path(directory)
    target_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = target_directory / f"utterance-{timestamp}-{uuid4().hex[:8]}.wav"
    target.write_bytes(audio)
    return target
