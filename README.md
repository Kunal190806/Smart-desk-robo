# 🤖 Mimobot Pro: Multimodal AI Desk Companion

Mimobot Pro is a state-of-the-art, cross-platform "Smart Desk Robot" ecosystem. It features an interactive Raspberry Pi display (The Face), a Windows Control Center for telemetry and automation, and an Android companion for seamless mobile integration.

---

## 🏗️ The Ecosystem

### 1. 🍓 Raspberry Pi (The Hub)
The "Heart" of Mimobot. Built in C++ using LVGL 8.3.
- **Autonomous Sleep/Wake:** Mochi goes to sleep after 5 minutes of inactivity; touch to wake.
- **Dynamic TileView:** 4-way swipe navigation (Stream Deck, Notifications, Telemetry, Media).
- **Sound Visualizer:** 10-bar real-time spectrum analyzer for PC audio.
- **Notification Feed:** Clean, card-based history with word-wrap and emoji sanitization.

### 2. 🖥️ Windows Control Center
Built in C# (WPF). The "Brain" that feeds data to the Pi.
- **Live Telemetry:** Sends CPU, GPU, RAM, and Disk stats every 2 seconds.
- **Stream Deck:** Customizable 6-button grid for app launches and macros.
- **Media Sync:** Detects Spotify/YouTube playback and relays track info.
- **Discord Integration:** Monitors voice channel activity.

### 3. 📱 Android Companion
The "Bridge." Built in Kotlin.
- **Smart Notification Relay:** Forwards phone alerts (WhatsApp, Discord, etc.) with emoji-to-text sanitization.
- **Calendar Sync:** Pulls the next 24h of events and triggers pre-event reminders on your desk.
- **Connection Manager:** Auto-reconnect engine to stay paired with the Pi.

---

## 🚀 Quick Start Guide

### I. Setting up the Pi
1. **Dependencies:**
   ```bash
   sudo apt-get update
   sudo apt-get install cmake libsdl2-dev libmpdclient-dev
   ```
2. **Build:**
   ```bash
   cd mimobot-cpp
   mkdir build && cd build
   cmake ..
   make -j4
   ```
3. **Auto-Start:**
   ```bash
   sudo cp ../mimobot.service /etc/systemd/system/
   sudo systemctl enable mimobot
   sudo systemctl start mimobot
   ```

### II. Setting up Windows
1. Open `mimobot-windows/MimobotControlCenter.sln` in Visual Studio 2022.
2. Build and Run. 
3. Enter your Raspberry Pi's IP address in the settings.

### III. Setting up Android
1. Open `mimobot-android` in Android Studio.
2. Build the APK and install it on your phone.
3. Grant **Notification Access** and **Calendar Access** when prompted.

---

## 📡 Communication Protocol (WebSocket)
Mimobot uses a lightweight JSON protocol over Port 8000.

| Packet Type | Description | Sample JSON |
| :--- | :--- | :--- |
| `NOTIF` | Phone Notifications | `{"type":"NOTIF", "app":"WA", "msg":"Hello"}` |
| `TELEMETRY` | PC Hardware Stats | `{"type":"TELEMETRY", "cpu":45, "gpu":60, ...}` |
| `REMINDER` | Calendar Events | `{"type":"REMINDER", "events":[...]}` |
| `AUDIO_VIZ` | Audio Data | `{"type":"AUDIO_VIZ", "v":[10, 45, 20, ...]}` |
| `ACTION` | Stream Deck Cmd | `{"type":"ACTION", "cmd":"launch_discord"}` |

---

## 🛠️ Tech Stack
- **Frontend:** LVGL (Light and Versatile Graphics Library)
- **Networking:** Mongoose Networking Library
- **OS:** Raspberry Pi OS (Lite) / Windows 10/11 / Android 12+
- **Languages:** C++, C#, Kotlin

---
