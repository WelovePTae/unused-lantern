from app.services.wake_word import WakeWordVerifier


def test_thai_wake_word_extracts_command_without_spaces() -> None:
    match = WakeWordVerifier().match("\u0e15\u0e35\u0e4b\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f")

    assert match.detected is True
    assert match.command_text == "\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f"


def test_alternative_wake_word_is_supported() -> None:
    match = WakeWordVerifier(alternatives=("tee",)).match("TEE \u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f")

    assert match.detected is True
    assert match.matched_phrase == "tee"


def test_wake_word_can_appear_before_command_in_a_sentence() -> None:
    match = WakeWordVerifier().match("\u0e0a\u0e48\u0e27\u0e22\u0e15\u0e35\u0e4b\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f\u0e2b\u0e19\u0e48\u0e2d\u0e22")

    assert match.detected is True
    assert match.command_text == "\u0e0a\u0e48\u0e27\u0e22 \u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f\u0e2b\u0e19\u0e48\u0e2d\u0e22"


def test_command_before_wake_word_is_preserved() -> None:
    match = WakeWordVerifier().match("\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f\u0e04\u0e38\u0e13\u0e2b\u0e32\u0e22\u0e15\u0e35\u0e4b")

    assert match.detected is True
    assert match.command_text == "\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f\u0e04\u0e38\u0e13\u0e2b\u0e32\u0e22"


def test_normalization_handles_punctuation_and_zero_width_space() -> None:
    match = WakeWordVerifier().match("\u0e15\u0e35\u0e4b\u200b, \u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f!")

    assert match.detected is True
    assert match.command_text == "\u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f"


def test_previous_lantern_wake_word_is_not_detected() -> None:
    assert WakeWordVerifier().verify("lantern \u0e40\u0e1b\u0e34\u0e14\u0e44\u0e1f") is False
