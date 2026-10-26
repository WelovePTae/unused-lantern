#include "audio_capture.h"

#include <driver/i2s.h>

#include "lantern_config.h"

namespace {
constexpr i2s_port_t kI2sPort = I2S_NUM_0;
}

void AudioCapture::begin() {
  i2s_config_t i2s_config = {};
  i2s_config.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX);
  i2s_config.sample_rate = static_cast<int>(lantern::kAudioSampleRateHz);
  i2s_config.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
  i2s_config.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  i2s_config.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  i2s_config.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  i2s_config.dma_buf_count = 4;
  i2s_config.dma_buf_len = lantern::kAudioFrameSamples;
  i2s_config.use_apll = false;
  i2s_config.tx_desc_auto_clear = false;
  i2s_config.fixed_mclk = 0;

  i2s_pin_config_t pin_config = {};
  pin_config.bck_io_num = lantern::pins::kI2sBclk;
  pin_config.ws_io_num = lantern::pins::kI2sWs;
  pin_config.data_out_num = I2S_PIN_NO_CHANGE;
  pin_config.data_in_num = lantern::pins::kI2sDataIn;

  const esp_err_t install_result = i2s_driver_install(kI2sPort, &i2s_config, 0, nullptr);
  if (install_result != ESP_OK) {
    Serial.printf("I2S driver install failed: %d\n", static_cast<int>(install_result));
    return;
  }

  const esp_err_t pin_result = i2s_set_pin(kI2sPort, &pin_config);
  if (pin_result != ESP_OK) {
    Serial.printf("I2S pin setup failed: %d\n", static_cast<int>(pin_result));
    return;
  }

  i2s_zero_dma_buffer(kI2sPort);
  Serial.println("I2S ready: 16 kHz mono PCM16 output");
}

bool AudioCapture::readFrame(int16_t* samples, size_t capacity, size_t* samples_read) {
  if (samples == nullptr || samples_read == nullptr ||
      capacity < lantern::kAudioFrameSamples) {
    return false;
  }

  int32_t raw_samples[lantern::kAudioFrameSamples] = {};
  size_t bytes_read = 0;
  const esp_err_t result = i2s_read(
      kI2sPort,
      raw_samples,
      sizeof(raw_samples),
      &bytes_read,
      portMAX_DELAY);
  if (result != ESP_OK || bytes_read != sizeof(raw_samples)) {
    *samples_read = 0;
    return false;
  }

  for (size_t index = 0; index < lantern::kAudioFrameSamples; ++index) {
    int32_t pcm16 = raw_samples[index] >> 14;
    if (pcm16 > 32767) pcm16 = 32767;
    if (pcm16 < -32768) pcm16 = -32768;
    samples[index] = static_cast<int16_t>(pcm16);
  }
  *samples_read = lantern::kAudioFrameSamples;
  return true;
}
