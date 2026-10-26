from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass, field
from typing import Protocol

from app.config import Settings
from app.audio import validate_wav
from app.schemas import Transcript


class ASRProvider(Protocol):
    """Common boundary for hosted and self-hosted Typhoon ASR."""

    name: str

    async def transcribe(
        self, audio: bytes, *, filename: str, content_type: str
    ) -> Transcript: ...


class ASRProviderError(RuntimeError):
    """A safe, user-facing ASR failure without credential details."""


@dataclass
class MockASRProvider:
    """Deterministic provider used by tests and local Phase 0 development."""

    text: str = ""
    name: str = "mock"

    async def transcribe(
        self, audio: bytes, *, filename: str, content_type: str
    ) -> Transcript:
        return Transcript(text=self.text, provider=self.name)


@dataclass
class TyphoonAPIProvider:
    """OpenAI-compatible hosted Typhoon file-transcription provider."""

    api_base_url: str
    model: str
    api_key: str | None
    timeout_s: float = 30.0
    client: object | None = field(default=None, repr=False)
    name: str = "typhoon_api"

    async def transcribe(
        self, audio: bytes, *, filename: str, content_type: str
    ) -> Transcript:
        validate_wav(audio)
        if not self.api_key and self.client is None:
            raise ASRProviderError("TYPHOON_API_KEY is not configured")
        try:
            text = await asyncio.to_thread(
                self._transcribe_sync, audio, filename, content_type
            )
        except ASRProviderError:
            raise
        except Exception as exc:
            raise ASRProviderError("Typhoon API transcription failed") from exc
        return Transcript(text=text, provider=self.name)

    def _transcribe_sync(self, audio: bytes, filename: str, content_type: str) -> str:
        if self.client is None:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base_url,
                timeout=self.timeout_s,
            )
        else:
            client = self.client

        audio_file = io.BytesIO(audio)
        audio_file.name = filename
        response = client.audio.transcriptions.create(
            file=audio_file,
            model=self.model,
        )
        text = getattr(response, "text", None)
        if not isinstance(text, str):
            raise ASRProviderError("Typhoon API returned no transcript text")
        return text.strip()


@dataclass
class TyphoonSelfHostedProvider:
    """Placeholder for a local `typhoon-asr` package/service adapter."""

    base_url: str
    name: str = "typhoon_self_hosted"

    async def transcribe(
        self, audio: bytes, *, filename: str, content_type: str
    ) -> Transcript:
        raise RuntimeError("Typhoon self-host provider is reserved for a later phase")


def create_asr_provider(settings: Settings) -> ASRProvider:
    provider = settings.asr_provider.lower()
    if provider == "mock":
        return MockASRProvider()
    if provider == "typhoon_api":
        return TyphoonAPIProvider(
            api_base_url=settings.typhoon_api_base_url,
            model=settings.typhoon_asr_model,
            api_key=settings.typhoon_api_key,
            timeout_s=settings.typhoon_api_timeout_s,
        )
    if provider == "typhoon_self_hosted":
        return TyphoonSelfHostedProvider(base_url=settings.typhoon_self_host_url)
    raise ValueError(f"Unsupported ASR_PROVIDER: {settings.asr_provider}")
