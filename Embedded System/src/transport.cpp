#include "transport.h"

#include <LittleFS.h>
#include <WiFi.h>
#include <esp_system.h>

#include <string.h>

#include "lantern_config.h"

namespace {
constexpr size_t kWriteChunkBytes = 512;
constexpr size_t kMaxResponseBytes = 4096;
const char* kBoundary = "----LanternAudioBoundary";

bool writeBytes(WiFiClient& client, const uint8_t* data, size_t length) {
  size_t offset = 0;
  while (offset < length) {
    const size_t chunk = min(kWriteChunkBytes, length - offset);
    const size_t written = client.write(data + offset, chunk);
    if (written == 0) return false;
    offset += written;
  }
  return true;
}

bool writeString(WiFiClient& client, const String& value) {
  return writeBytes(
      client,
      reinterpret_cast<const uint8_t*>(value.c_str()),
      value.length());
}

void putUint32LE(uint8_t* target, uint32_t value) {
  target[0] = value & 0xff;
  target[1] = (value >> 8) & 0xff;
  target[2] = (value >> 16) & 0xff;
  target[3] = (value >> 24) & 0xff;
}

void putUint16LE(uint8_t* target, uint16_t value) {
  target[0] = value & 0xff;
  target[1] = (value >> 8) & 0xff;
}

void makeWavHeader(uint8_t* header, size_t pcm_bytes) {
  memset(header, 0, 44);
  memcpy(header, "RIFF", 4);
  putUint32LE(header + 4, 36 + pcm_bytes);
  memcpy(header + 8, "WAVEfmt ", 8);
  putUint32LE(header + 16, 16);
  putUint16LE(header + 20, 1);
  putUint16LE(header + 22, 1);
  putUint32LE(header + 24, lantern::kAudioSampleRateHz);
  putUint32LE(header + 28, lantern::kAudioSampleRateHz * 2);
  putUint16LE(header + 32, 2);
  putUint16LE(header + 34, 16);
  memcpy(header + 36, "data", 4);
  putUint32LE(header + 40, pcm_bytes);
}

uint32_t boundedBackoff(uint32_t base, uint32_t maximum, uint8_t retry_index) {
  uint32_t delay_ms = base;
  for (uint8_t index = 0; index < retry_index && delay_ms < maximum; ++index) {
    delay_ms = min(maximum, delay_ms * 2);
  }
  return delay_ms;
}
}  // namespace

void BackendTransport::begin() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  if (!ensureWiFi()) {
    Serial.println("Wi-Fi startup connection failed; upload will retry later");
  }
}

bool BackendTransport::ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  if (strlen(LANTERN_WIFI_SSID) == 0) {
    Serial.println("Wi-Fi credentials are not configured in secrets.h");
    return false;
  }

  for (uint8_t attempt = 0; attempt < lantern::kWifiMaxAttempts; ++attempt) {
    Serial.printf(
        "Wi-Fi connect attempt %u/%u: %s\n",
        attempt + 1,
        lantern::kWifiMaxAttempts,
        LANTERN_WIFI_SSID);
    WiFi.begin(LANTERN_WIFI_SSID, LANTERN_WIFI_PASSWORD);
    const uint32_t started_at = millis();
    while (WiFi.status() != WL_CONNECTED &&
           millis() - started_at < lantern::kWifiConnectTimeoutMs) {
      delay(250);
      Serial.print('.');
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("Wi-Fi connected, IP: ");
      Serial.println(WiFi.localIP());
      return true;
    }

    Serial.printf("Wi-Fi attempt %u timed out\n", attempt + 1);
    if (attempt + 1 < lantern::kWifiMaxAttempts) {
      const uint32_t backoff_ms = boundedBackoff(
          lantern::kWifiBackoffBaseMs,
          lantern::kWifiBackoffMaxMs,
          attempt);
      Serial.printf("Wi-Fi reconnect backoff: %lu ms\n",
                    static_cast<unsigned long>(backoff_ms));
      delay(backoff_ms);
    }
  }

  Serial.println("Wi-Fi reconnect exhausted; audio upload deferred");
  return false;
}

String BackendTransport::nextRequestId() {
  static uint32_t sequence = 0;
  static const uint32_t boot_nonce = esp_random();
  ++sequence;
  return String("esp32-") + String(boot_nonce, HEX) + "-" +
         String(millis(), HEX) + "-" + String(sequence, HEX);
}

BackendTransport::AttemptResult BackendTransport::sendWavAttempt(
    const char* pcm_path,
    size_t sample_count,
    const String& request_id,
    String* response) {
  const uint32_t attempt_started_ms = millis();
  const size_t pcm_bytes = sample_count * sizeof(int16_t);
  File pcm_file = LittleFS.open(pcm_path, FILE_READ);
  if (!pcm_file || pcm_file.size() != pcm_bytes) {
    Serial.println("Audio staging file missing or has invalid size");
    return AttemptResult::kPermanentFailure;
  }

  WiFiClient client;
  client.setTimeout(lantern::kHttpTimeoutMs);
  if (!client.connect(
          LANTERN_BACKEND_HOST,
          LANTERN_BACKEND_PORT,
          static_cast<int32_t>(lantern::kHttpTimeoutMs))) {
    Serial.println("Backend TCP connection failed");
    return AttemptResult::kRetryableFailure;
  }

  const size_t wav_bytes = 44 + pcm_bytes;
  const String prefix = String("--") + kBoundary +
      "\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"utterance.wav\"\r\n"
      "Content-Type: audio/wav\r\n\r\n";
  const String suffix = String("\r\n--") + kBoundary + "--\r\n";
  const size_t content_length = prefix.length() + wav_bytes + suffix.length();

  client.print(String("POST ") + LANTERN_BACKEND_PATH + " HTTP/1.1\r\n");
  client.print(String("Host: ") + LANTERN_BACKEND_HOST + "\r\n");
  client.print(String("X-Lantern-Request-ID: ") + request_id + "\r\n");
  client.print(String("Content-Type: multipart/form-data; boundary=") +
               kBoundary + "\r\n");
  client.print(String("Content-Length: ") + content_length + "\r\n");
  client.print("Connection: close\r\n\r\n");

  uint8_t wav_header[44];
  makeWavHeader(wav_header, pcm_bytes);
  if (!writeString(client, prefix) ||
      !writeBytes(client, wav_header, sizeof(wav_header))) {
    Serial.println("Audio upload write failed");
    client.stop();
    pcm_file.close();
    return AttemptResult::kRetryableFailure;
  }

  uint8_t chunk[kWriteChunkBytes];
  size_t remaining = pcm_bytes;
  while (remaining > 0) {
    const size_t requested = min(remaining, sizeof(chunk));
    const size_t read = pcm_file.read(chunk, requested);
    if (read == 0 || !writeBytes(client, chunk, read)) {
      Serial.println("Audio staging read/upload failed");
      client.stop();
      pcm_file.close();
      return AttemptResult::kRetryableFailure;
    }
    remaining -= read;
  }
  pcm_file.close();
  if (!writeString(client, suffix)) {
    Serial.println("Audio upload suffix write failed");
    client.stop();
    return AttemptResult::kRetryableFailure;
  }

  const String status_line = client.readStringUntil('\n');
  if (status_line.length() < 12 || !status_line.startsWith("HTTP/")) {
    Serial.println("Backend response timeout or malformed status line");
    client.stop();
    return AttemptResult::kRetryableFailure;
  }
  const int status_code = status_line.substring(9, 12).toInt();
  while (client.connected()) {
    const String line = client.readStringUntil('\n');
    if (line == "\r" || line.length() == 0) break;
  }

  *response = "";
  response->reserve(kMaxResponseBytes);
  const uint32_t response_started_at = millis();
  while ((client.connected() || client.available()) &&
         millis() - response_started_at < lantern::kHttpTimeoutMs &&
         response->length() < kMaxResponseBytes) {
    if (client.available()) {
      *response += static_cast<char>(client.read());
    } else {
      delay(1);
    }
  }
  client.stop();
  Serial.printf("Backend HTTP status: %d request_id=%s http_attempt_ms=%lu\n",
                status_code,
                request_id.c_str(),
                static_cast<unsigned long>(millis() - attempt_started_ms));

  if (status_code >= 200 && status_code < 300 && response->length() > 0) {
    return AttemptResult::kSuccess;
  }
  if (status_code >= 400 && status_code < 500) {
    return AttemptResult::kPermanentFailure;
  }
  return AttemptResult::kRetryableFailure;
}

bool BackendTransport::sendWavFile(
    const char* pcm_path,
    size_t sample_count,
    String* response) {
  if (pcm_path == nullptr || sample_count == 0 || response == nullptr) {
    Serial.println("Audio upload rejected: invalid buffer");
    return false;
  }
  if (sample_count > lantern::kMaxRecordingSamples) {
    Serial.println("Audio upload rejected: sample count exceeds configured bound");
    return false;
  }

  const String request_id = nextRequestId();
  const uint32_t upload_started_ms = millis();
  *response = "";
  for (uint8_t attempt = 0; attempt < lantern::kUploadMaxAttempts; ++attempt) {
    Serial.printf(
        "Audio upload attempt %u/%u request_id=%s\n",
        attempt + 1,
        lantern::kUploadMaxAttempts,
        request_id.c_str());
    if (!ensureWiFi()) {
      if (attempt + 1 < lantern::kUploadMaxAttempts) {
        const uint32_t backoff_ms = boundedBackoff(
            lantern::kUploadBackoffBaseMs,
            lantern::kUploadBackoffMaxMs,
            attempt);
        Serial.printf("Upload retry backoff: %lu ms\n",
                      static_cast<unsigned long>(backoff_ms));
        delay(backoff_ms);
      }
      continue;
    }

    const AttemptResult result =
        sendWavAttempt(pcm_path, sample_count, request_id, response);
    if (result == AttemptResult::kSuccess) {
      Serial.printf(
          "PIPELINE upload_attempts=%u upload_total_ms=%lu result=ok\n",
          attempt + 1,
          static_cast<unsigned long>(millis() - upload_started_ms));
      return true;
    }
    if (result == AttemptResult::kPermanentFailure) {
      Serial.println("Audio upload rejected by backend; no retry");
      return false;
    }
    if (attempt + 1 < lantern::kUploadMaxAttempts) {
      const uint32_t backoff_ms = boundedBackoff(
          lantern::kUploadBackoffBaseMs,
          lantern::kUploadBackoffMaxMs,
          attempt);
      Serial.printf("Audio upload retry backoff: %lu ms\n",
                    static_cast<unsigned long>(backoff_ms));
      delay(backoff_ms);
    }
  }

  Serial.printf("Audio upload failed after %u attempts; utterance discarded\n",
                lantern::kUploadMaxAttempts);
  Serial.printf(
      "PIPELINE upload_attempts=%u upload_total_ms=%lu result=failed\n",
      lantern::kUploadMaxAttempts,
      static_cast<unsigned long>(millis() - upload_started_ms));
  return false;
}
