import asyncio
from types import SimpleNamespace

from app.audio import pcm16_to_wav
from app.services.asr import ASRProviderError, TyphoonAPIProvider


class FakeTranscriptions:
    def __init__(self, response=None, error=None) -> None:
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, transcriptions) -> None:
        self.audio = SimpleNamespace(transcriptions=transcriptions)


def valid_wav() -> bytes:
    return pcm16_to_wav(b"\x00\x00" * 320)


def test_typhoon_provider_uses_openai_compatible_file_api() -> None:
    transcriptions = FakeTranscriptions(SimpleNamespace(text="สวัสดี Lantern"))
    provider = TyphoonAPIProvider(
        api_base_url="https://api.opentyphoon.ai/v1",
        model="typhoon-asr-realtime",
        api_key="test-key",
        client=FakeClient(transcriptions),
    )

    result = asyncio.run(
        provider.transcribe(valid_wav(), filename="utterance.wav", content_type="audio/wav")
    )

    assert result.text == "สวัสดี Lantern"
    assert transcriptions.calls[0]["model"] == "typhoon-asr-realtime"
    assert transcriptions.calls[0]["file"].name == "utterance.wav"


def test_typhoon_provider_reports_api_error_without_secret_details() -> None:
    transcriptions = FakeTranscriptions(error=RuntimeError("network failure"))
    provider = TyphoonAPIProvider(
        api_base_url="https://api.opentyphoon.ai/v1",
        model="typhoon-asr-realtime",
        api_key="secret-value",
        client=FakeClient(transcriptions),
    )

    try:
        asyncio.run(
            provider.transcribe(valid_wav(), filename="utterance.wav", content_type="audio/wav")
        )
    except ASRProviderError as exc:
        assert "secret-value" not in str(exc)
    else:
        raise AssertionError("ASRProviderError was not raised")
