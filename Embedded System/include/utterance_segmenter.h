#pragma once

#include <Arduino.h>
#include <FS.h>

#include "lantern_config.h"

class UtteranceSegmenter {
 public:
  enum class CompletionReason : uint8_t {
    kNone,
    kSilenceTimeout,
    kMaximumDuration,
    kManualFlush,
    kStorageError,
  };

  bool begin();
  void reset();
  bool processFrame(const int16_t* samples, size_t sample_count, bool speech);
  bool flush();

  bool active() const { return recording_; }
  const char* pcmPath() const { return kPcmPath; }
  size_t sampleCount() const { return utterance_sample_count_; }
  uint16_t recordingMs() const { return recording_ms_; }
  uint16_t silenceMs() const { return silence_ms_; }
  CompletionReason completionReason() const { return completion_reason_; }
  const char* completionReasonName() const;

 private:
  static constexpr const char* kPcmPath = "/lantern_utterance.pcm";

  void pushPreRoll(const int16_t* samples, size_t sample_count);
  bool startRecording();
  bool copyPreRollToFile();
  bool appendToFile(const int16_t* samples, size_t sample_count);
  void finalizeFile();
  void discardFile();
  void clearState();

  bool storage_ready_ = false;
  File utterance_file_;
  int16_t pre_roll_[lantern::kPreRollSamples] = {};
  size_t pre_roll_count_ = 0;
  size_t pre_roll_write_index_ = 0;
  size_t utterance_sample_count_ = 0;
  uint16_t speech_ms_ = 0;
  uint16_t silence_ms_ = 0;
  uint16_t recording_ms_ = 0;
  bool recording_ = false;
  CompletionReason completion_reason_ = CompletionReason::kNone;
};
