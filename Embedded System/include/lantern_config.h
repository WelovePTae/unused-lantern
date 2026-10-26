#pragma once

#include <Arduino.h>

#if __has_include("secrets.h")
#include "secrets.h"
#endif

#ifndef LANTERN_WIFI_SSID
#define LANTERN_WIFI_SSID ""
#endif

#ifndef LANTERN_WIFI_PASSWORD
#define LANTERN_WIFI_PASSWORD ""
#endif

#ifndef LANTERN_BACKEND_HOST
#define LANTERN_BACKEND_HOST "192.168.137.1"
#endif

#ifndef LANTERN_BACKEND_PORT
#define LANTERN_BACKEND_PORT 8000
#endif

#ifndef LANTERN_BACKEND_PATH
#define LANTERN_BACKEND_PATH "/v1/utterances/transcribe"
#endif

#ifndef LANTERN_MAX_RECORDING_MS
#define LANTERN_MAX_RECORDING_MS 4000
#endif

#ifndef RELAY_ACTIVE_LOW
#define RELAY_ACTIVE_LOW 1
#endif

namespace lantern {
namespace pins {
constexpr gpio_num_t kI2sBclk = GPIO_NUM_26;
constexpr gpio_num_t kI2sWs = GPIO_NUM_25;
constexpr gpio_num_t kI2sDataIn = GPIO_NUM_33;
// LED anode connects through a resistor to GPIO17; cathode connects to GND.
constexpr uint8_t kDemoLed = 17;
// Relay module signal only; never connect the relay coil to this GPIO.
// GPIO23 is reserved for the verified low-voltage relay input.
constexpr uint8_t kRelayControl = 23;
}  // namespace pins

constexpr bool kRelayActiveLow = RELAY_ACTIVE_LOW != 0;

constexpr uint32_t kAudioSampleRateHz = 16000;
constexpr uint16_t kAudioFrameMs = 20;
constexpr size_t kAudioFrameSamples =
    kAudioSampleRateHz * kAudioFrameMs / 1000;
constexpr uint16_t kPreRollMs = 300;
constexpr size_t kPreRollSamples = kAudioSampleRateHz * kPreRollMs / 1000;
constexpr uint16_t kSilenceTimeoutMs = 500;
constexpr uint16_t kMinimumSpeechMs = 200;
// Audio is staged in LittleFS; only the 300 ms pre-roll remains in DRAM.
constexpr uint16_t kMaxRecordingMs =
    static_cast<uint16_t>(LANTERN_MAX_RECORDING_MS);
constexpr size_t kMaxRecordingSamples =
    kAudioSampleRateHz * kMaxRecordingMs / 1000;
constexpr uint16_t kVadMeanAbsoluteThreshold = 700;
// Lightweight preprocessing for INMP441 input. Increase the gate only if the
// physical microphone setup has a consistently loud noise floor.
constexpr uint16_t kNoiseGateThreshold = 120;
constexpr int32_t kHighPassFeedbackNumerator = 995;
constexpr int32_t kHighPassFeedbackDenominator = 1000;
constexpr uint32_t kSignalTelemetryIntervalMs = 1000;
constexpr uint32_t kWifiConnectTimeoutMs = 8000;
constexpr uint8_t kWifiMaxAttempts = 4;
constexpr uint32_t kWifiBackoffBaseMs = 250;
constexpr uint32_t kWifiBackoffMaxMs = 4000;
// Typhoon provider timeout is 30 seconds; leave margin for HTTP transport.
constexpr uint32_t kHttpTimeoutMs = 35000;
constexpr uint8_t kUploadMaxAttempts = 3;
constexpr uint32_t kUploadBackoffBaseMs = 500;
constexpr uint32_t kUploadBackoffMaxMs = 4000;
constexpr uint8_t kExecutedRequestCacheSize = 8;
}  // namespace lantern
