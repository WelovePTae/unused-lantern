#pragma once

#include <Arduino.h>

class AudioFilter {
 public:
  void reset();
  void process(int16_t* samples, size_t sample_count);

 private:
  int32_t previous_input_ = 0;
  int32_t previous_output_ = 0;
};
