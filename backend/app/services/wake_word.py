from __future__ import annotations

from dataclasses import dataclass

from app.services.text_normalization import normalize_text


DEFAULT_THAI_WAKE_WORD = "\u0e15\u0e35\u0e4b"
DEFAULT_WAKE_ALTERNATIVES = (
    "tee",
    "\u0e15\u0e35",
    "\u0e17\u0e35",
)


@dataclass(frozen=True)
class WakeWordMatch:
    detected: bool
    normalized_text: str
    matched_phrase: str | None = None
    command_text: str = ""


@dataclass(frozen=True)
class WakeWordVerifier:
    """Transcript-level wake-word verifier; on-device wake word is not claimed."""

    phrase: str = DEFAULT_THAI_WAKE_WORD
    alternatives: tuple[str, ...] = DEFAULT_WAKE_ALTERNATIVES

    def _candidates(self) -> tuple[str, ...]:
        candidates = {
            normalized
            for value in (self.phrase, *self.alternatives)
            if (normalized := normalize_text(value))
        }
        return tuple(sorted(candidates, key=len, reverse=True))

    def match(self, transcript: str) -> WakeWordMatch:
        normalized = normalize_text(transcript)
        for candidate in self._candidates():
            search_from = 0
            while (index := normalized.find(candidate, search_from)) >= 0:
                command_start = index + len(candidate)
                before = normalized[index - 1] if index else ""
                after = normalized[command_start] if command_start < len(normalized) else ""
                if (
                    candidate[-1].isascii()
                    and candidate[-1].isalnum()
                    and (
                        (before and before.isascii() and before.isalnum())
                        or (after and after.isascii() and after.isalnum())
                    )
                ):
                    search_from = index + 1
                    continue

                return WakeWordMatch(
                    detected=True,
                    normalized_text=normalized,
                    matched_phrase=candidate,
                    # Typhoon may place the wake word at the end of a Thai
                    # sentence, so keep text from both sides for intent parsing.
                    command_text=normalize_text(
                        f"{normalized[:index]} {normalized[command_start:]}"
                    ),
                )

        return WakeWordMatch(detected=False, normalized_text=normalized)

    def verify(self, transcript: str) -> bool:
        return self.match(transcript).detected
