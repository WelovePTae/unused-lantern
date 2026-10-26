from __future__ import annotations

import hashlib
import time


class DuplicateSegmentGuard:
    """Bounded in-memory guard against replaying the same uploaded audio."""

    def __init__(self, window_seconds: float = 30.0, max_entries: int = 128) -> None:
        self.window_seconds = max(0.0, window_seconds)
        self.max_entries = max(1, max_entries)
        self._reserved: dict[str, float] = {}

    def _digest(self, audio: bytes) -> str:
        return hashlib.sha256(audio).hexdigest()

    def _purge(self, now: float) -> None:
        cutoff = now - self.window_seconds
        expired = [
            digest
            for digest, timestamp in self._reserved.items()
            if timestamp < cutoff
        ]
        for digest in expired:
            self._reserved.pop(digest, None)

    def reserve(self, audio: bytes) -> bool:
        now = time.monotonic()
        if self.window_seconds == 0:
            return True
        self._purge(now)
        digest = self._digest(audio)
        if digest in self._reserved:
            return False
        self._reserved[digest] = now
        while len(self._reserved) > self.max_entries:
            oldest = min(self._reserved, key=self._reserved.get)
            self._reserved.pop(oldest, None)
        return True

    def release(self, audio: bytes) -> None:
        self._reserved.pop(self._digest(audio), None)
