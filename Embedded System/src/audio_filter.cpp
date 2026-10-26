#include "audio_filter.h"

#include <stdint.h>

#include "lantern_config.h"

namespace {
int16_t clampPcm16(int32_t sample) {
  if (sample > 32767) return 32767;
  if (sample < -32768) return -32768;
  return static_cast<int16_t>(sample);
}
}  // namespace

void AudioFilter::reset() {
  previous_input_ = 0;
  previous_output_ = 0;
}

void AudioFilter::process(int16_t* samples, size_t sample_count) {
  if (samples == nullptr) return;

  for (size_t index = 0; index < sample_count; ++index) {
    const int32_t input = samples[index];
    const int32_t high_passed =
        input - previous_input_ +
        (previous_output_ * lantern::kHighPassFeedbackNumerator) /
            lantern::kHighPassFeedbackDenominator;
    previous_input_ = input;

    const int16_t filtered = clampPcm16(high_passed);
    previous_output_ = filtered;
    samples[index] =
        abs(filtered) < lantern::kNoiseGateThreshold ? 0 : filtered;
  }
}
