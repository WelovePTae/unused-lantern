#include "command_handler.h"

#include "lantern_config.h"

namespace {
bool containsIntent(const String& response, const char* intent) {
  const String compact = String("\"name\":\"") + intent + "\"";
  const String spaced = String("\"name\": \"") + intent + "\"";
  return response.indexOf(compact) >= 0 || response.indexOf(spaced) >= 0;
}

bool isAccepted(const String& response) {
  return response.indexOf("\"accepted\":true") >= 0 ||
         response.indexOf("\"accepted\": true") >= 0;
}

bool hasWakeWord(const String& response) {
  return response.indexOf("\"wake_word_detected\":true") >= 0 ||
         response.indexOf("\"wake_word_detected\": true") >= 0;
}

String extractRequestId(const String& response) {
  String marker = "\"request_id\":\"";
  const int start = response.indexOf(marker);
  int value_start = start;
  if (start < 0) {
    marker = "\"request_id\": \"";
    value_start = response.indexOf(marker);
  }
  if (value_start < 0) return "";
  value_start += marker.length();
  const int value_end = response.indexOf('"', value_start);
  if (value_end < 0) return "";
  return response.substring(value_start, value_end);
}
}  // namespace

bool CommandHandler::hasExecutedRequest(const String& request_id) const {
  if (request_id.length() == 0) return false;
  for (uint8_t index = 0; index < executed_request_count_; ++index) {
    if (executed_request_ids_[index] == request_id) return true;
  }
  return false;
}

void CommandHandler::rememberExecutedRequest(const String& request_id) {
  if (request_id.length() == 0 || hasExecutedRequest(request_id)) return;
  executed_request_ids_[executed_request_next_] = request_id;
  executed_request_next_ =
      (executed_request_next_ + 1) % lantern::kExecutedRequestCacheSize;
  if (executed_request_count_ < lantern::kExecutedRequestCacheSize) {
    ++executed_request_count_;
  }
}

void CommandHandler::begin(RelayController* relay_controller) {
  relay_controller_ = relay_controller;
  if (relay_controller_ != nullptr) {
    relay_controller_->begin();
  }
  pinMode(lantern::pins::kDemoLed, OUTPUT);
  setDemoLed(false);
  Serial.println("Command handler ready; low-voltage demo LED on GPIO17");
  Serial.println("Serial test commands: LED ON, LED OFF");
  if (relay_controller_ != nullptr) {
    Serial.println("Relay voice integration ready on GPIO23");
  }
}

void CommandHandler::setDemoLed(bool enabled) {
  digitalWrite(lantern::pins::kDemoLed, enabled ? HIGH : LOW);
  Serial.printf("Demo LED: %s\n", enabled ? "ON" : "OFF");
}

void CommandHandler::handleSerialCommand(const String& command) {
  String normalized = command;
  normalized.trim();
  normalized.toUpperCase();
  if (normalized == "LED ON" || normalized == "ON") {
    setDemoLed(true);
  } else if (normalized == "LED OFF" || normalized == "OFF") {
    setDemoLed(false);
  } else {
    Serial.println("Unknown LED command; use LED ON or LED OFF");
  }
}

void CommandHandler::handleBackendResponse(const String& response) {
  Serial.print("Backend response: ");
  Serial.println(response);
  const uint32_t handler_started_us = micros();
  const String request_id = extractRequestId(response);
  const bool accepted = isAccepted(response);
  const bool wake_word_detected = hasWakeWord(response);
  const bool light_on = containsIntent(response, "LIGHT_ON");
  const bool light_off = containsIntent(response, "LIGHT_OFF");
  const uint32_t response_parse_us = micros() - handler_started_us;
  Serial.printf(
      "PIPELINE response_parse_us=%lu\n",
      static_cast<unsigned long>(response_parse_us));
  Serial.printf(
      "Backend decision: intent=%s accepted=%s wake_word=%s request_id=%s\n",
      light_on && !light_off ? "LIGHT_ON"
                             : light_off && !light_on ? "LIGHT_OFF" : "OTHER",
      accepted ? "true" : "false",
      wake_word_detected ? "true" : "false",
      request_id.length() > 0 ? request_id.c_str() : "none");
  if (!accepted) {
    Serial.println("Relay/LED command rejected: backend accepted=false");
    return;
  }
  if (!wake_word_detected) {
    Serial.println("Relay/LED command rejected: wake word missing");
    return;
  }
  if (hasExecutedRequest(request_id)) {
    Serial.printf("Duplicate backend command ignored request_id=%s\n",
                  request_id.c_str());
    return;
  }
  if (light_on == light_off) {
    Serial.println("Invalid backend response: expected one LIGHT_ON/OFF intent");
    return;
  }
  const bool requested_on = light_on;
  if (relay_controller_ != nullptr) {
    const bool previous = relay_controller_->isOn();
    const uint32_t relay_started_us = micros();
    Serial.printf(
        "Relay request: requested=%s previous=%s\n",
        requested_on ? "ON" : "OFF",
        previous ? "ON" : "OFF");
    relay_controller_->setState(requested_on);
    Serial.printf(
        "Relay result: state=%s\n",
        relay_controller_->isOn() ? "ON" : "OFF");
    Serial.printf(
        "PIPELINE relay_gpio_us=%lu\n",
        static_cast<unsigned long>(micros() - relay_started_us));
  } else {
    Serial.println("Relay command ignored: controller unavailable");
  }
  setDemoLed(requested_on);
  rememberExecutedRequest(request_id);
}
