import logging

import pytest
from fastapi.testclient import TestClient

from app.audio import pcm16_to_wav
from app.config import Settings
from app.main import create_app
from app.services.asr import MockASRProvider


class CountingMockASRProvider(MockASRProvider):
    calls: int = 0

    async def transcribe(self, audio: bytes, *, filename: str, content_type: str):
        self.calls += 1
        return await super().transcribe(
            audio,
            filename=filename,
            content_type=content_type,
        )


def wav_fixture() -> bytes:
    return pcm16_to_wav(b"\x00\x00" * 160)


def test_health() -> None:
    client = TestClient(create_app(Settings()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_transcribe_uses_mock_asr_and_allowlisted_intent() -> None:
    application = create_app(Settings(wake_phrase="lantern"))
    application.state.asr_provider = MockASRProvider("Lantern \u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f")
    client = TestClient(application)

    response = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json()["wake_word_detected"] is True
    assert response.json()["intent"]["name"] == "LIGHT_ON"


def test_transcribe_accepts_wake_word_and_command_inside_sentence() -> None:
    application = create_app(Settings(require_wake_word=True))
    application.state.asr_provider = MockASRProvider(
        "\u0e0a\u0e48\u0e27\u0e22\u0e15\u0e35\u0e4b\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f\u0e2b\u0e19\u0e48\u0e2d\u0e22"
    )
    client = TestClient(application)

    response = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["wake_word_detected"] is True
    assert payload["intent"]["name"] == "LIGHT_ON"
    assert payload["intent"]["accepted"] is True


def test_transcribe_accepts_command_before_wake_word() -> None:
    application = create_app(Settings(require_wake_word=True))
    application.state.asr_provider = MockASRProvider(
        "\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f\u0e04\u0e38\u0e13\u0e2b\u0e32\u0e22\u0e15\u0e35"
    )
    client = TestClient(application)

    response = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["wake_word_detected"] is True
    assert payload["intent"]["name"] == "LIGHT_ON"
    assert payload["intent"]["accepted"] is True


def test_transcribe_without_wake_word_is_ignored() -> None:
    application = create_app(Settings(require_wake_word=True))
    application.state.asr_provider = MockASRProvider("\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f")
    client = TestClient(application)

    response = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json()["wake_word_detected"] is False
    assert response.json()["intent"]["name"] == "IGNORE"
    assert response.json()["intent"]["accepted"] is False


@pytest.mark.parametrize(
    ("transcript", "expected_intent"),
    [
        (
            "\u0e2d\u0e32\u0e08\u0e32\u0e23\u0e22\u0e4c\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f\u0e43\u0e2b\u0e49\u0e2b\u0e19\u0e48\u0e2d\u0e22",
            "LIGHT_ON",
        ),
        ("\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f", "LIGHT_ON"),
        (
            "\u0e0a\u0e48\u0e27\u0e22\u0e1b\u0e34\u0e14\u0e44\u0e1f\u0e2b\u0e19\u0e48\u0e2d\u0e22",
            "LIGHT_OFF",
        ),
        ("\u0e1b\u0e34\u0e14\u0e44\u0e1f", "LIGHT_OFF"),
    ],
)
def test_transcribe_without_wake_word_accepts_clear_thai_light_command(
    transcript: str, expected_intent: str
) -> None:
    application = create_app(Settings(require_wake_word=False))
    application.state.asr_provider = MockASRProvider(transcript)
    client = TestClient(application)

    response = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["wake_word_detected"] is False
    assert payload["matched_wake_word"] is None
    assert payload["intent"]["name"] == expected_intent
    assert payload["intent"]["accepted"] is True


def test_no_wake_word_mode_rejects_unrelated_command() -> None:
    application = create_app(Settings(require_wake_word=False))
    application.state.asr_provider = MockASRProvider(
        "\u0e27\u0e31\u0e19\u0e19\u0e35\u0e49\u0e2d\u0e32\u0e01\u0e32\u0e28\u0e14\u0e35"
    )
    client = TestClient(application)

    response = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    assert response.json()["intent"]["name"] == "UNKNOWN_INTENT"
    assert response.json()["intent"]["accepted"] is False


def test_no_wake_word_mode_rejects_negated_command() -> None:
    application = create_app(Settings(require_wake_word=False))
    application.state.asr_provider = MockASRProvider(
        "\u0e44\u0e21\u0e48\u0e15\u0e49\u0e2d\u0e07\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f"
    )
    client = TestClient(application)

    response = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    assert response.json()["intent"]["name"] == "UNKNOWN_INTENT"
    assert response.json()["intent"]["accepted"] is False


def test_transcribe_logs_recognized_text(caplog) -> None:
    application = create_app(Settings())
    text = "\u0e17\u0e14\u0e2a\u0e2d\u0e1a\u0e40\u0e2a\u0e35\u0e22\u0e07"
    application.state.asr_provider = MockASRProvider(text)
    client = TestClient(application)
    caplog.set_level(logging.INFO, logger="lantern.asr")

    response = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    assert response.status_code == 200
    assert text in caplog.text


def test_transcribe_logs_pipeline_latency_stages(caplog) -> None:
    application = create_app(Settings())
    application.state.asr_provider = MockASRProvider("\u0e15\u0e35\u0e4b \u0e40\u0e1b\u0e34\u0e14")
    client = TestClient(application)
    caplog.set_level(logging.INFO, logger="lantern.asr")

    response = client.post(
        "/v1/utterances/transcribe",
        headers={"X-Lantern-Request-ID": "latency-test-1"},
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    assert response.status_code == 200
    assert "pipeline_latency_ms" in caplog.text
    assert "asr=" in caplog.text
    assert "wake_word=" in caplog.text
    assert "intent=" in caplog.text
    assert "total=" in caplog.text


def test_non_wav_is_rejected_before_asr() -> None:
    client = TestClient(create_app(Settings()))

    response = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.txt", b"not audio", "text/plain")},
    )

    assert response.status_code == 400


def test_malformed_wav_is_rejected_before_asr() -> None:
    client = TestClient(create_app(Settings()))

    response = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", b"RIFFxxxxWAVE", "audio/wav")},
    )

    assert response.status_code == 400


def test_duplicate_audio_is_ignored_without_second_asr_call() -> None:
    application = create_app(Settings())
    provider = CountingMockASRProvider(
        "\u0e15\u0e35\u0e4b \u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f"
    )
    application.state.asr_provider = provider
    client = TestClient(application)

    first = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )
    second = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    assert first.json()["intent"]["name"] == "LIGHT_ON"
    assert second.json()["duplicate_segment"] is True
    assert second.json()["intent"]["name"] == "IGNORE"
    assert provider.calls == 1


def test_request_id_replays_cached_response_without_second_asr_call() -> None:
    application = create_app(Settings())
    provider = CountingMockASRProvider(
        "\u0e15\u0e35\u0e4b \u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f"
    )
    application.state.asr_provider = provider
    client = TestClient(application)
    headers = {"X-Lantern-Request-ID": "esp32-test-002"}

    first = client.post(
        "/v1/utterances/transcribe",
        headers=headers,
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )
    replay = client.post(
        "/v1/utterances/transcribe",
        headers=headers,
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["replayed_request"] is True
    assert replay.json()["intent"]["name"] == "LIGHT_ON"
    assert provider.calls == 1


def test_invalid_request_id_is_rejected() -> None:
    client = TestClient(create_app(Settings()))

    response = client.post(
        "/v1/utterances/transcribe",
        headers={"X-Lantern-Request-ID": "bad request id"},
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    assert response.status_code == 400


def test_uploaded_wav_can_be_saved_for_debugging(tmp_path) -> None:
    application = create_app(
        Settings(save_uploaded_audio=True, audio_save_dir=str(tmp_path))
    )
    application.state.asr_provider = MockASRProvider("\u0e17\u0e14\u0e2a\u0e2d\u0e1a\u0e40\u0e2a\u0e35\u0e22\u0e07")
    client = TestClient(application)

    response = client.post(
        "/v1/utterances/transcribe",
        files={"audio": ("utterance.wav", wav_fixture(), "audio/wav")},
    )

    assert response.status_code == 200
    saved_files = list(tmp_path.glob("utterance-*.wav"))
    assert len(saved_files) == 1
    assert saved_files[0].read_bytes() == wav_fixture()
