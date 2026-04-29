# 🦾 Mimobot Pro: Master Manual

Welcome to your "Pro" grade smart assistant ecosystem. This manual explains how to link your Raspberry Pi, Windows PC, and Android Phone into a single, seamless brain.

---

## 🛠️ Step 1: The Mimobot Hub (Raspberry Pi)
The Pi is the "Server." It must be running first for the others to connect.

### Setup
1. **Move Folder**: Copy the `mimobot-cpp` folder to your Pi.
2. **Install Tools**: 
   ```bash
   sudo apt update
   sudo apt install cmake g++ libmpdclient-dev libsdl2-dev mpd mpc -y
   ```
3. **Build**:
   ```bash
   cd mimobot-cpp && mkdir build && cd build
   cmake .. && make -j4
   ```
4. **Run**: `./MimobotPro`

> [!TIP]
> Make a note of your Pi's IP address (run `hostname -I`). You will need this for the other apps.

---

## 💻 Step 2: The Control Center (Windows)
This app lets you manage your shortcuts and executes commands sent from the Pi.

### Setup
1. Open the `mimobot-windows` project in **Visual Studio**.
2. **IP Config**: In `MainWindow.xaml.cs`, find the line `ws = new WebSocket("ws://192.168.1.100:8000")` and replace the IP with your Pi's IP.
3. **Compile**: Press `F5` to build and run.
4. **Mapping**: Drag any `.exe` (like Discord or a Game) onto the tiles and hit **SYNC ALL**.

---

## 📱 Step 3: The Notification Sensor (Android)
This app beams your phone's notifications to your Mimobot screen.

### Setup
1. Open the `mimobot-android` project in **Android Studio**.
2. **IP Config**: In `MimoNotificationService.kt`, update the WebSocket URL with your Pi's IP.
3. **Install**: Run the app on your phone.
4. **Grant Access**: Open the app and tap **"Enable Mimobot Notification Access."** Find "Mimobot Sensor" in the list and allow it.

---

## 🎮 Daily Operation

1. **Music**: Play music on your Pi using MPD/Spotify. The Mimobot will show the song title and artist automatically. Use the touch screen to skip songs.
2. **Shortcuts**: Tap any of the 6 tiles on the Mimobot touch screen to instantly launch that app on your PC.
3. **Notifications**: Whenever you get a message on your phone, a sleek bar will slide down at the top of the Mimobot face.

---

## 📦 Dependencies Checklist

| Component | Library Required | Install Command |
| :--- | :--- | :--- |
| **Android** | `OkHttp` | Add `implementation("com.squareup.okhttp3:okhttp:4.12.0")` to `build.gradle` |
| **Windows** | `WebSocketSharp` | Right-click Project -> Manage NuGet Packages -> Search "WebSocketSharp" |
| **Pi (C++)** | `libmpdclient` | `sudo apt install libmpdclient-dev` |
| **Pi (Network)** | `Mongoose` | Download `mongoose.c` and `mongoose.h` into `src/network/` |

---

## 🔧 Troubleshooting
- **Connection Failed?**: Ensure all devices are on the same Wi-Fi network.
- **Buttons don't launch apps?**: Make sure the Windows app is running and showing the "● Connected" status.
- **No Music Info?**: Ensure `mpd` is running on your Pi (`sudo service mpd start`).
- **UI looks small?**: Adjust the resolution in `main.cpp` (current: 320x240).

---

## 🎨 Premium UI Tips
To get the "Glow" and "Smooth" effects seen in the mockups, ensure your `lv_conf.h` has these enabled:
- `#define LV_USE_SHADOW 1` (For glowing eyes)
- `#define LV_USE_FONT_MONTSERRAT_24 1` (For high-res text)
- `#define LV_COLOR_DEPTH 32` (For perfect gradients)
