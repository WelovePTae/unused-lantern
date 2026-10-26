#include <Arduino.h>

#include "lantern_config.h"
#include "relay_controller.h"

RelayController relay;

void printHelp() {
  Serial.println("Relay standalone test commands: ON, OFF, TOGGLE, STATUS, HELP");
  Serial.println("This mode does not start I2S, Wi-Fi, HTTP, ASR, or voice control.");
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(25);
  relay.begin();
  printHelp();
}

void loop() {
  if (!Serial.available()) return;

  String command = Serial.readStringUntil('\n');
  command.trim();
  command.toUpperCase();

  if (command == "ON") {
    relay.setOn();
  } else if (command == "OFF") {
    relay.setOff();
  } else if (command == "TOGGLE") {
    relay.setState(!relay.isOn());
  } else if (command == "STATUS") {
    Serial.printf("Relay state: %s\n", relay.isOn() ? "ON" : "OFF");
  } else if (command == "HELP" || command.length() == 0) {
    printHelp();
  } else {
    Serial.println("Invalid relay command; use ON, OFF, TOGGLE, STATUS, or HELP");
  }
}
