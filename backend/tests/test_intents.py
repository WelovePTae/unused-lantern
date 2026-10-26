import pytest

from app.services.intents import IntentDetector


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("เปิดไฟหน่อย", "LIGHT_ON"),
        ("ดับไฟ", "LIGHT_OFF"),
        ("เปิดพัดลม", "FAN_ON"),
        ("หยุดพัดลม", "FAN_OFF"),
    ],
)
def test_allowlisted_thai_commands(command: str, expected: str) -> None:
    decision = IntentDetector().detect(command)

    assert decision.name == expected
    assert decision.accepted is True


@pytest.mark.parametrize(
    ("command", "expected"),
    [("\u0e40\u0e1b\u0e34\u0e14", "LIGHT_ON"), ("\u0e1b\u0e34\u0e14", "LIGHT_OFF")],
)
def test_short_light_verbs_are_supported(command: str, expected: str) -> None:
    decision = IntentDetector().detect(command)

    assert decision.name == expected
    assert decision.accepted is True


def test_short_light_verbs_do_not_match_longer_device_commands() -> None:
    decision = IntentDetector().detect("\u0e40\u0e1b\u0e34\u0e14\u0e1e\u0e31\u0e14\u0e25\u0e21")

    assert decision.name == "FAN_ON"
    assert decision.accepted is True


def test_open_and_close_words_can_be_found_in_a_sentence() -> None:
    detector = IntentDetector()

    assert detector.detect("\u0e40\u0e1b\u0e34\u0e14\u0e04\u0e38\u0e13\u0e2b\u0e32\u0e22").name == "LIGHT_ON"
    assert detector.detect("\u0e0a\u0e48\u0e27\u0e22\u0e1b\u0e34\u0e14\u0e2b\u0e19\u0e48\u0e2d\u0e22").name == "LIGHT_OFF"


def test_unknown_command_is_rejected() -> None:
    decision = IntentDetector().detect("วันนี้อากาศดี")

    assert decision.name == "UNKNOWN_INTENT"
    assert decision.accepted is False


def test_contradictory_command_is_rejected() -> None:
    decision = IntentDetector().detect("เปิดไฟแล้วปิดไฟ")

    assert decision.name == "UNKNOWN_INTENT"
    assert decision.reason == "contradictory commands"


def test_multiple_device_commands_are_rejected() -> None:
    decision = IntentDetector().detect("เปิดไฟและเปิดพัดลม")

    assert decision.name == "UNKNOWN_INTENT"
    assert decision.reason == "ambiguous multiple commands"


def test_negative_command_is_rejected() -> None:
    decision = IntentDetector().detect("อย่าเปิดไฟ")

    assert decision.name == "UNKNOWN_INTENT"
    assert decision.accepted is False
