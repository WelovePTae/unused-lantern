import unittest
import json


class FakeGpio:
    def __init__(self) -> None:
        self.mode = None
        self.writes: list[int] = []

    def pin_mode_output(self) -> None:
        self.mode = "OUTPUT"

    def write(self, level: int) -> None:
        self.writes.append(level)


class RelayModel:
    """Host-only model of RelayController for polarity and dedupe checks."""

    def __init__(self, active_low: bool, gpio: FakeGpio) -> None:
        self.active_low = active_low
        self.gpio = gpio
        self.initialized = False
        self.on = False

    def begin(self) -> None:
        self.gpio.pin_mode_output()
        self.gpio.write(self.level_for(False))
        self.initialized = True
        self.on = False

    def set_state(self, on: bool) -> None:
        if not self.initialized or self.on == on:
            return
        self.gpio.write(self.level_for(on))
        self.on = on

    def level_for(self, on: bool) -> int:
        return 0 if (on == self.active_low) else 1


class RelayControllerTests(unittest.TestCase):
    def test_active_low_initial_off_and_on(self) -> None:
        gpio = FakeGpio()
        relay = RelayModel(active_low=True, gpio=gpio)

        relay.begin()
        relay.set_state(True)

        self.assertEqual(gpio.mode, "OUTPUT")
        self.assertEqual(gpio.writes, [1, 0])

    def test_active_high_initial_off_and_on(self) -> None:
        gpio = FakeGpio()
        relay = RelayModel(active_low=False, gpio=gpio)

        relay.begin()
        relay.set_state(True)

        self.assertEqual(gpio.writes, [0, 1])

    def test_repeated_state_does_not_switch_again(self) -> None:
        gpio = FakeGpio()
        relay = RelayModel(active_low=True, gpio=gpio)
        relay.begin()

        relay.set_state(False)
        relay.set_state(True)
        relay.set_state(True)
        relay.set_state(False)
        relay.set_state(False)

        self.assertEqual(gpio.writes, [1, 0, 1])

    def test_command_before_begin_is_ignored(self) -> None:
        gpio = FakeGpio()
        relay = RelayModel(active_low=True, gpio=gpio)

        relay.set_state(True)

        self.assertEqual(gpio.writes, [])
        self.assertFalse(relay.on)


class BackendRelayModel:
    """Host-only model of the Stage B JSON acceptance boundary."""

    def __init__(self) -> None:
        self.relay = RelayModel(active_low=True, gpio=FakeGpio())
        self.relay.begin()
        self.executed_request_ids: list[str] = []

    def handle(self, response: str) -> str:
        try:
            payload = json.loads(response)
            intent = payload["intent"]
            accepted = intent["accepted"] is True
            wake_detected = payload["wake_word_detected"] is True
            name = intent["name"]
            request_id = payload.get("request_id")
        except (KeyError, TypeError, json.JSONDecodeError):
            return "invalid"

        if not accepted or not wake_detected:
            return "rejected"
        if request_id and request_id in self.executed_request_ids:
            return "duplicate"
        if name not in {"LIGHT_ON", "LIGHT_OFF"}:
            return "invalid"

        self.relay.set_state(name == "LIGHT_ON")
        if request_id:
            self.executed_request_ids.append(request_id)
            self.executed_request_ids = self.executed_request_ids[-8:]
        return "applied"


def backend_response(
    name: str = "LIGHT_ON",
    *,
    accepted: bool = True,
    wake_word_detected: bool = True,
    request_id: str = "esp32-test-1",
) -> str:
    return json.dumps(
        {
            "transcript": {"text": "ตี๋ เปิดไฟ", "provider": "mock"},
            "wake_word_detected": wake_word_detected,
            "request_id": request_id,
            "intent": {
                "name": name,
                "parameters": {},
                "accepted": accepted,
                "reason": "test",
            },
        }
    )


class BackendResponseTests(unittest.TestCase):
    def test_accepted_light_on_and_off(self) -> None:
        controller = BackendRelayModel()

        self.assertEqual(controller.handle(backend_response()), "applied")
        self.assertTrue(controller.relay.on)
        self.assertEqual(
            controller.handle(
                backend_response(name="LIGHT_OFF", request_id="esp32-test-2")
            ),
            "applied",
        )
        self.assertFalse(controller.relay.on)

    def test_rejected_and_missing_wake_word_do_not_change_state(self) -> None:
        controller = BackendRelayModel()

        self.assertEqual(
            controller.handle(backend_response(accepted=False)), "rejected"
        )
        self.assertEqual(
            controller.handle(backend_response(wake_word_detected=False)), "rejected"
        )
        self.assertFalse(controller.relay.on)

    def test_duplicate_request_id_is_ignored(self) -> None:
        controller = BackendRelayModel()

        self.assertEqual(controller.handle(backend_response()), "applied")
        self.assertEqual(controller.handle(backend_response()), "duplicate")
        self.assertEqual(controller.relay.gpio.writes, [1, 0])

    def test_old_request_id_is_still_ignored_after_new_commands(self) -> None:
        controller = BackendRelayModel()

        self.assertEqual(
            controller.handle(backend_response(request_id="request-a")), "applied"
        )
        self.assertEqual(
            controller.handle(
                backend_response(name="LIGHT_OFF", request_id="request-b")
            ),
            "applied",
        )
        self.assertEqual(
            controller.handle(backend_response(request_id="request-a")), "duplicate"
        )
        self.assertEqual(controller.relay.gpio.writes, [1, 0, 1])

    def test_invalid_or_unsupported_response_is_ignored(self) -> None:
        controller = BackendRelayModel()

        self.assertEqual(controller.handle("not-json"), "invalid")
        self.assertEqual(
            controller.handle(backend_response(name="FAN_ON")), "invalid"
        )
        self.assertFalse(controller.relay.on)

    def test_network_reconnect_without_new_response_keeps_state(self) -> None:
        controller = BackendRelayModel()
        self.assertEqual(controller.handle(backend_response()), "applied")

        # A disconnect/reconnect event itself contains no accepted command.
        self.assertTrue(controller.relay.on)
        self.assertEqual(controller.relay.gpio.writes, [1, 0])


if __name__ == "__main__":
    unittest.main()
