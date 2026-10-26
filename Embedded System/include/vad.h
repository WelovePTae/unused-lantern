#pragma once

#include <Arduino.h>

class VoiceActivityGate {
 public:
  bool speechDetected(const int16_t* samples, size_t sample_count) const;
};
