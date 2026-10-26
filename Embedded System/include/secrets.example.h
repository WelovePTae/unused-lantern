#pragma once

// Copy this file to secrets.h and set values for the local Wi-Fi only.
// Do not commit secrets.h.
#define LANTERN_WIFI_SSID "your-wifi-name"
#define LANTERN_WIFI_PASSWORD "your-wifi-password"

// Use the computer's LAN IP, not 127.0.0.1, when the backend runs on a PC.
#define LANTERN_BACKEND_HOST "192.168.137.1"
#define LANTERN_BACKEND_PORT 8000
#define LANTERN_BACKEND_PATH "/v1/utterances/transcribe"
