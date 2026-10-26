from app.services.deduplication import DuplicateSegmentGuard


def test_duplicate_segment_is_reserved_once() -> None:
    guard = DuplicateSegmentGuard(window_seconds=30)

    assert guard.reserve(b"same audio") is True
    assert guard.reserve(b"same audio") is False
    assert guard.reserve(b"different audio") is True


def test_failed_segment_can_be_released_for_retry() -> None:
    guard = DuplicateSegmentGuard(window_seconds=30)

    assert guard.reserve(b"retry me") is True
    guard.release(b"retry me")
    assert guard.reserve(b"retry me") is True
