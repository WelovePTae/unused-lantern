#pragma once

#include <Arduino.h>

class AudioCapture {
 public:
  void begin();
  bool readFrame(int16_t* samples, size_t capacity, size_t* samples_read);
};
