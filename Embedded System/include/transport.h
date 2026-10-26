#pragma once

#include <Arduino.h>

class BackendTransport {
 public:
  void begin();
  bool sendWavFile(const char* pcm_path, size_t sample_count, String* response);

 private:
  enum class AttemptResult { kSuccess, kRetryableFailure, kPermanentFailure };

  bool ensureWiFi();
  AttemptResult sendWavAttempt(
      const char* pcm_path,
      size_t sample_count,
      const String& request_id,
      String* response);
  String nextRequestId();
};
