#pragma once

#include <Arduino.h>

class RelayController {
 public:
  void begin();
  void setOn();
  void setOff();
  void setState(bool on);
  bool isOn() const { return relay_on_; }

 private:
  uint8_t levelFor(bool on) const;

  bool initialized_ = false;
  bool relay_on_ = false;
};
