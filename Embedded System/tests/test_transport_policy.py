import unittest


class BoundedUploadModel:
    """Host-only model of the firmware's bounded retry policy."""

    def __init__(self, max_attempts: int = 3) -> None:
        self.max_attempts = max_attempts
        self.request_id = "esp32-boot-utterance-1"
        self.attempts: list[str] = []

    def send(self, outcomes: list[str]) -> bool:
        for outcome in outcomes[: self.max_attempts]:
            self.attempts.append(self.request_id)
            if outcome == "success":
                return True
            if outcome == "permanent_failure":
                return False
        return False


class TransportPolicyTests(unittest.TestCase):
    def test_timeout_retries_with_same_request_id_and_stops_at_limit(self) -> None:
        transport = BoundedUploadModel(max_attempts=3)

        self.assertFalse(transport.send(["timeout", "timeout", "timeout", "success"]))
        self.assertEqual(len(transport.attempts), 3)
        self.assertEqual(set(transport.attempts), {"esp32-boot-utterance-1"})

    def test_wifi_reconnect_then_success_reuses_request_id(self) -> None:
        transport = BoundedUploadModel(max_attempts=3)

        self.assertTrue(transport.send(["wifi_failure", "success"]))
        self.assertEqual(transport.attempts, [
            "esp32-boot-utterance-1",
            "esp32-boot-utterance-1",
        ])

    def test_permanent_backend_error_is_not_retried(self) -> None:
        transport = BoundedUploadModel(max_attempts=3)

        self.assertFalse(transport.send(["permanent_failure", "success"]))
        self.assertEqual(len(transport.attempts), 1)


if __name__ == "__main__":
    unittest.main()
