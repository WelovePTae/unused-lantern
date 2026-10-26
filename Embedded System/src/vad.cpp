#include "vad.h"

#include <stdint.h>

#include "lantern_config.h"

bool VoiceActivityGate::speechDetected(
    const int16_t* samples,
    size_t sample_count) const {
  if (samples == nullptr || sample_count == 0) return false;

  uint64_t absolute_sum = 0;
  for (size_t index = 0; index < sample_count; ++index) {
    const int32_t sample = samples[index];
    absolute_sum += static_cast<uint32_t>(sample < 0 ? -sample : sample);
  }
  const uint32_t mean_absolute = absolute_sum / sample_count;
  return mean_absolute >= lantern::kVadMeanAbsoluteThreshold;
}
