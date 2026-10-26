from __future__ import annotations

import time

from app.schemas import UtteranceResponse


class RequestReplayCache:
    """Bounded in-memory cache for idempotent retries from one ESP32 utterance."""

    def __init__(self, window_seconds: float = 60.0, max_entries: int = 128) -> None:
        self.window_seconds = max(0.0, window_seconds)
        self.max_entries = max(1, max_entries)
        self._responses: dict[str, tuple[float, UtteranceResponse]] = {}

    def _purge(self, now: float) -> None:
        cutoff = now - self.window_seconds
        expired = [
            request_id
            for request_id, (timestamp, _) in self._responses.items()
            if timestamp < cutoff
        ]
        for request_id in expired:
            self._responses.pop(request_id, None)

    def get(self, request_id: str) -> UtteranceResponse | None:
        now = time.monotonic()
        self._purge(now)
        entry = self._responses.get(request_id)
        return entry[1] if entry else None

    def put(self, request_id: str, response: UtteranceResponse) -> None:
        now = time.monotonic()
        self._purge(now)
        self._responses[request_id] = (now, response)
        while len(self._responses) > self.max_entries:
            oldest = min(self._responses, key=lambda key: self._responses[key][0])
            self._responses.pop(oldest, None)
