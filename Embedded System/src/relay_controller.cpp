#include "relay_controller.h"

#include "lantern_config.h"

namespace {
const char* stateName(bool on) {
  return on ? "ON" : "OFF";
}
}  // namespace

void RelayController::begin() {
  // This is the earliest firmware-controlled OFF state. ESP32 reset and
  // bootloader time are outside this class's control; see the documentation.
  const uint8_t off_level = levelFor(false);
  // Preload the output latch before enabling the pin. This reduces the
  // setup-time transition window but cannot control ROM/bootloader reset state.
  digitalWrite(lantern::pins::kRelayControl, off_level);
  pinMode(lantern::pins::kRelayControl, OUTPUT);
  relay_on_ = false;
  digitalWrite(lantern::pins::kRelayControl, off_level);
  initialized_ = true;
  Serial.printf(
      "Relay controller ready: GPIO%u active-%s state=OFF\n",
      lantern::pins::kRelayControl,
      lantern::kRelayActiveLow ? "LOW" : "HIGH");
}

void RelayController::setOn() {
  setState(true);
}

void RelayController::setOff() {
  setState(false);
}

void RelayController::setState(bool on) {
  if (!initialized_) {
    Serial.println("Relay command ignored: controller is not initialized");
    return;
  }
  if (relay_on_ == on) {
    Serial.printf("Relay unchanged: %s\n", stateName(on));
    return;
  }
  digitalWrite(lantern::pins::kRelayControl, levelFor(on));
  relay_on_ = on;
  Serial.printf("Relay state: %s\n", stateName(on));
}

uint8_t RelayController::levelFor(bool on) const {
  const bool output_high = lantern::kRelayActiveLow ? !on : on;
  return output_high ? HIGH : LOW;
}
