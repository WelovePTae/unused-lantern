#include "utterance_segmenter.h"

#include <LittleFS.h>

#include <string.h>

#include "lantern_config.h"

bool UtteranceSegmenter::begin() {
  // This partition is used only for temporary utterances. Auto-format lets a
  // fresh board initialize it without a separate filesystem upload step.
  storage_ready_ = LittleFS.begin(true);
  if (!storage_ready_) {
    Serial.println("LittleFS mount failed; long utterance staging unavailable");
    return false;
  }
  LittleFS.remove(kPcmPath);
  Serial.println("LittleFS ready: utterances staged outside internal DRAM");
  return true;
}

void UtteranceSegmenter::reset() {
  discardFile();
  pre_roll_count_ = 0;
  pre_roll_write_index_ = 0;
  completion_reason_ = CompletionReason::kNone;
  clearState();
}

bool UtteranceSegmenter::processFrame(
    const int16_t* samples,
    size_t sample_count,
    bool speech) {
  if (!storage_ready_ || samples == nullptr ||
      sample_count != lantern::kAudioFrameSamples) {
    return false;
  }

  if (!recording_) {
    pushPreRoll(samples, sample_count);
    if (!speech) return false;

    if (!startRecording() || !copyPreRollToFile()) {
      completion_reason_ = CompletionReason::kStorageError;
      discardFile();
      clearState();
      Serial.println("Utterance staging failed; continuing to listen");
      return false;
    }
    recording_ = true;
    completion_reason_ = CompletionReason::kNone;
    speech_ms_ = lantern::kAudioFrameMs;
    silence_ms_ = 0;
    recording_ms_ = static_cast<uint16_t>(
        utterance_sample_count_ * 1000 / lantern::kAudioSampleRateHz);
    return false;
  }

  if (!appendToFile(samples, sample_count)) {
    completion_reason_ = CompletionReason::kStorageError;
    Serial.println("Utterance flash write failed; discarding segment");
    discardFile();
    clearState();
    return false;
  }
  recording_ms_ += lantern::kAudioFrameMs;
  if (speech) {
    speech_ms_ += lantern::kAudioFrameMs;
    silence_ms_ = 0;
  } else {
    silence_ms_ += lantern::kAudioFrameMs;
  }

  if (silence_ms_ >= lantern::kSilenceTimeoutMs ||
      recording_ms_ >= lantern::kMaxRecordingMs) {
    completion_reason_ = recording_ms_ >= lantern::kMaxRecordingMs
                             ? CompletionReason::kMaximumDuration
                             : CompletionReason::kSilenceTimeout;
    recording_ = false;
    finalizeFile();
    if (speech_ms_ >= lantern::kMinimumSpeechMs) return true;
    discardFile();
    clearState();
  }
  return false;
}

bool UtteranceSegmenter::flush() {
  if (!recording_) return false;
  completion_reason_ = CompletionReason::kManualFlush;
  recording_ = false;
  finalizeFile();
  if (speech_ms_ >= lantern::kMinimumSpeechMs) return true;
  discardFile();
  clearState();
  return false;
}

void UtteranceSegmenter::pushPreRoll(
    const int16_t* samples,
    size_t sample_count) {
  for (size_t index = 0; index < sample_count; ++index) {
    if (pre_roll_count_ < lantern::kPreRollSamples) {
      pre_roll_[pre_roll_count_++] = samples[index];
    } else {
      pre_roll_[pre_roll_write_index_] = samples[index];
      pre_roll_write_index_ =
          (pre_roll_write_index_ + 1) % lantern::kPreRollSamples;
    }
  }
}

bool UtteranceSegmenter::startRecording() {
  LittleFS.remove(kPcmPath);
  utterance_file_ = LittleFS.open(kPcmPath, FILE_WRITE);
  utterance_sample_count_ = 0;
  return static_cast<bool>(utterance_file_);
}

bool UtteranceSegmenter::copyPreRollToFile() {
  if (pre_roll_count_ == 0) return true;
  const size_t start = pre_roll_count_ == lantern::kPreRollSamples
                           ? pre_roll_write_index_
                           : 0;
  const size_t first_count = min(
      pre_roll_count_, lantern::kPreRollSamples - start);
  if (!appendToFile(&pre_roll_[start], first_count)) return false;
  if (first_count < pre_roll_count_) {
    if (!appendToFile(&pre_roll_[0], pre_roll_count_ - first_count)) {
      return false;
    }
  }
  return true;
}

bool UtteranceSegmenter::appendToFile(
    const int16_t* samples,
    size_t sample_count) {
  if (!utterance_file_ ||
      utterance_sample_count_ + sample_count > lantern::kMaxRecordingSamples) {
    return false;
  }
  const size_t bytes = sample_count * sizeof(int16_t);
  if (utterance_file_.write(
          reinterpret_cast<const uint8_t*>(samples), bytes) != bytes) {
    return false;
  }
  utterance_sample_count_ += sample_count;
  return true;
}

void UtteranceSegmenter::finalizeFile() {
  if (utterance_file_) utterance_file_.close();
}

void UtteranceSegmenter::discardFile() {
  if (utterance_file_) utterance_file_.close();
  if (storage_ready_) LittleFS.remove(kPcmPath);
}

void UtteranceSegmenter::clearState() {
  pre_roll_count_ = 0;
  pre_roll_write_index_ = 0;
  utterance_sample_count_ = 0;
  speech_ms_ = 0;
  silence_ms_ = 0;
  recording_ms_ = 0;
  recording_ = false;
}

const char* UtteranceSegmenter::completionReasonName() const {
  switch (completion_reason_) {
    case CompletionReason::kSilenceTimeout:
      return "silence_timeout";
    case CompletionReason::kMaximumDuration:
      return "maximum_duration";
    case CompletionReason::kManualFlush:
      return "manual_flush";
    case CompletionReason::kStorageError:
      return "storage_error";
    case CompletionReason::kNone:
    default:
      return "none";
  }
}
