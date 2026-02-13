/*
  esp32_mimobot.ino
  Firmware for ESP32-C3 (Main Controller) - MIMOBOT Smart Desk Companion

  Responsibilities:
  - Date & time (NTP)
  - Reminders & alerts
  - Stopwatch
  - Pomodoro timer
  - OLED display (SSD1306) with simple animations/emotions
  - Mobile notification placeholders (WiFi/NTP + simple HTTP stub)
  - Touch sensor (TTP223) input for mode switching / acknowledge
  - UART communication with ATmega328 for sensor data

  Notes:
  - Uses non-blocking timing (millis()) throughout
  - Modular functions for UI, timers, UART, sensors
  - Pin assignments may need adjustment depending on board
*/

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <time.h>

// ---------- CONFIG ----------
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
#define OLED_ADDRESS  0x3C
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Replace with your WiFi credentials for NTP / mobile notification testing
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";

// UART pins for ESP32-C3 -> ATmega328 (adjust as needed)
#define UART_BAUD 115200
#define ATMEGA_RX_PIN 10 // ESP32 TX -> ATmega RX
#define ATMEGA_TX_PIN 9  // ESP32 RX <- ATmega TX

// Touch sensor (TTP223) digital output
#define TOUCH_PIN 5

// UI / animation
const unsigned long ANIM_INTERVAL = 300; // ms

// Timing and state machine
enum SystemState { STATE_IDLE, STATE_CLOCK, STATE_REMINDER_ALERT, STATE_STOPWATCH, STATE_POMODORO, STATE_NOTIFICATION };
volatile SystemState systemState = STATE_IDLE;

// Stopwatch
bool swRunning = false;
unsigned long swStart = 0;
unsigned long swElapsed = 0;

// Pomodoro (default 25/5 minutes)
const unsigned long POMODORO_WORK_MS = 25UL * 60UL * 1000UL;
const unsigned long POMODORO_BREAK_MS = 5UL * 60UL * 1000UL;
bool pomRunning = false;
bool pomOnBreak = false;
unsigned long pomStart = 0;

// Reminders (simple example) - times in epoch seconds
struct Reminder { time_t when; const char* text; bool active; };
Reminder reminders[4];

// Sensor storage (updated via UART)
float sensorTemp = NAN;
String sensorLight = "UNKNOWN";
String sensorProx = "UNKNOWN";
unsigned long lastSensorRequest = 0;
const unsigned long SENSOR_REQUEST_INTERVAL = 5000; // ms

// Display animation state
unsigned long lastAnim = 0;
int animFrame = 0;

// Serial input buffer from ATmega
String uartBuf = "";

// ---------- FUNCTION DECLARATIONS ----------
void initDisplay();
void displayUpdate();
void displayClock();
void displaySensors();
void displayEmotion(int frame);
void connectWiFi();
void syncTime();
void checkReminders();
void addSampleReminders();
void handleTouch();
void switchStateNext();
void requestSensorData();
void parseSensorLine(const String &line);
void handleUART();
String formattedTime();

// ---------- SETUP ----------
void setup() {
  Serial.begin(115200); // USB logging
  // Begin UART to ATmega using second serial port
  Serial1.begin(UART_BAUD, SERIAL_8N1, ATMEGA_TX_PIN, ATMEGA_RX_PIN);

  pinMode(TOUCH_PIN, INPUT);

  initDisplay();
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0,0);
  display.println("MIMOBOT Starting...");
  display.display();

  connectWiFi();
  syncTime();

  addSampleReminders();

  lastAnim = millis();
  lastSensorRequest = 0;
}

// ---------- MAIN LOOP ----------
void loop() {
  unsigned long now = millis();

  handleTouch();
  handleUART();

  // Periodically request sensors
  if (now - lastSensorRequest >= SENSOR_REQUEST_INTERVAL) {
    requestSensorData();
    lastSensorRequest = now;
  }

  // Check reminders by comparing with current epoch time
  checkReminders();

  // Non-blocking animation update
  if (now - lastAnim >= ANIM_INTERVAL) {
    animFrame = (animFrame + 1) % 4;
    lastAnim = now;
  }

  // Update display depending on state
  displayUpdate();

  // Simple stopwatch/pomodoro handling (no blocking)
  if (swRunning) {
    swElapsed = millis() - swStart;
  }
  if (pomRunning) {
    unsigned long elapsed = millis() - pomStart;
    if (!pomOnBreak && elapsed >= POMODORO_WORK_MS) {
      // switch to break
      pomOnBreak = true;
      pomStart = millis();
      systemState = STATE_REMINDER_ALERT;
    } else if (pomOnBreak && elapsed >= POMODORO_BREAK_MS) {
      // pomodoro complete
      pomRunning = false;
      pomOnBreak = false;
      systemState = STATE_NOTIFICATION;
    }
  }

  delay(10); // small yield
}

// ---------- DISPLAY & UI ----------
void initDisplay() {
  Wire.begin();
  if(!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println("SSD1306 allocation failed");
    for(;;);
  }
}

void displayUpdate() {
  display.clearDisplay();
  switch(systemState) {
    case STATE_IDLE:
      display.setTextSize(1);
      display.setCursor(0,0);
      display.println("MIMOBOT - Idle");
      display.println(formattedTime());
      displaySensors();
      displayEmotion(animFrame);
      break;
    case STATE_CLOCK:
      displayClock();
      break;
    case STATE_REMINDER_ALERT:
      display.setTextSize(1);
      display.setCursor(0,0);
      display.println("REMINDER ALERT");
      display.println("Press touch to ACK");
      break;
    case STATE_STOPWATCH:
      display.setTextSize(1);
      display.setCursor(0,0);
      display.println("Stopwatch");
      unsigned long ms = swElapsed;
      unsigned int s = (ms/1000)%60;
      unsigned int m = (ms/60000)%60;
      unsigned int h = ms/3600000;
      char buf[32];
      sprintf(buf, "%02u:%02u:%02u", h, m, s);
      display.println(buf);
      break;
    case STATE_POMODORO:
      display.setTextSize(1);
      display.setCursor(0,0);
      display.println("Pomodoro");
      if (pomRunning) {
        unsigned long elapsed = millis() - pomStart;
        unsigned long remaining = (pomOnBreak) ? (POMODORO_BREAK_MS - elapsed) : (POMODORO_WORK_MS - elapsed);
        unsigned int s = (remaining/1000)%60;
        unsigned int m = (remaining/60000)%60;
        char buf[32];
        sprintf(buf, "%02u:%02u", m, s);
        display.println((pomOnBreak)?"Break:" : "Work:");
        display.println(buf);
      } else {
        display.println("Stopped");
      }
      break;
    case STATE_NOTIFICATION:
      display.setTextSize(1);
      display.setCursor(0,0);
      display.println("Notification");
      display.println("(See mobile)");
      break;
  }
  display.display();
}

void displayClock() {
  display.setTextSize(2);
  display.setCursor(0,0);
  display.println(formattedTime());
  display.setTextSize(1);
  display.setCursor(0,36);
  displaySensors();
  displayEmotion(animFrame);
}

void displaySensors() {
  display.setTextSize(1);
  display.setCursor(0,20);
  display.print("Temp:");
  if (!isnan(sensorTemp)) display.print(sensorTemp,1); else display.print("--");
  display.print(" C  ");
  display.print("Light:");
  display.print(sensorLight);
}

void displayEmotion(int frame) {
  // Very simple emoticon using rectangles/lines
  int x = 96, y = 8;
  // ... draw simple frames
  display.drawRect(x,y,28,28,SSD1306_WHITE);
  if (frame % 4 == 0) {
    // happy
    display.fillRect(x+6,y+16,6,2,SSD1306_WHITE);
    display.fillRect(x+16,y+16,6,2,SSD1306_WHITE);
    display.drawCircle(x+8,y+10,2,SSD1306_WHITE);
    display.drawCircle(x+20,y+10,2,SSD1306_WHITE);
  } else if (frame % 4 == 1) {
    // blink
    display.drawLine(x+6,y+10,x+10,y+10,SSD1306_WHITE);
    display.drawLine(x+18,y+10,x+22,y+10,SSD1306_WHITE);
    display.fillRect(x+6,y+18,14,2,SSD1306_WHITE);
  } else if (frame % 4 == 2) {
    // surprised
    display.drawCircle(x+8,y+10,2,SSD1306_WHITE);
    display.drawCircle(x+20,y+10,2,SSD1306_WHITE);
    display.drawCircle(x+14,y+18,3,SSD1306_WHITE);
  } else {
    // neutral
    display.drawCircle(x+8,y+10,2,SSD1306_WHITE);
    display.drawCircle(x+20,y+10,2,SSD1306_WHITE);
    display.drawLine(x+6,y+20,x+22,y+20,SSD1306_WHITE);
  }
}

// ---------- TOUCH & INPUT ----------
void handleTouch() {
  static int lastState = LOW;
  int val = digitalRead(TOUCH_PIN);
  if (val == HIGH && lastState == LOW) {
    // Rising edge - toggle modes
    switchStateNext();
  }
  lastState = val;
}

void switchStateNext() {
  // Cycle through states
  if (systemState == STATE_IDLE) systemState = STATE_CLOCK;
  else if (systemState == STATE_CLOCK) systemState = STATE_STOPWATCH;
  else if (systemState == STATE_STOPWATCH) systemState = STATE_POMODORO;
  else if (systemState == STATE_POMODORO) systemState = STATE_NOTIFICATION;
  else systemState = STATE_IDLE;
}

// ---------- REMINDERS ----------
void addSampleReminders() {
  time_t now;
  time(&now);
  reminders[0].when = now + 30; // 30s from now
  reminders[0].text = "Stand up stretch";
  reminders[0].active = true;
  for (int i=1;i<4;i++) reminders[i].active=false;
}

void checkReminders() {
  time_t now;
  time(&now);
  for (int i=0;i<4;i++) {
    if (reminders[i].active && reminders[i].when <= now) {
      // Trigger reminder
      systemState = STATE_REMINDER_ALERT;
      // once triggered, deactivate
      reminders[i].active = false;
      // In a full build we would also send mobile notification here
      Serial.println("Reminder triggered: "+String(reminders[i].text));
    }
  }
}

// ---------- UART COMM WITH ATMEGA ----------
void requestSensorData() {
  // Ask ATmega for current sensor data
  Serial1.print("REQ\n");
}

void handleUART() {
  while (Serial1.available()) {
    char c = (char)Serial1.read();
    if (c == '\n') {
      String line = uartBuf;
      uartBuf = "";
      if (line.length() > 0) parseSensorLine(line);
    } else if (c != '\r') {
      uartBuf += c;
    }
  }
}

void parseSensorLine(const String &line) {
  // Expected formats: TEMP:27.3 or LIGHT:DIM or PROX:USER_PRESENT
  if (line.startsWith("TEMP:")) {
    String val = line.substring(5);
    sensorTemp = val.toFloat();
  } else if (line.startsWith("LIGHT:")) {
    sensorLight = line.substring(6);
  } else if (line.startsWith("PROX:")) {
    sensorProx = line.substring(5);
  }
  // For debugging
  Serial.println("ATmega -> " + line);
}

// ---------- TIME & WIFI ----------
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 8000) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi connected");
  } else {
    Serial.println("WiFi failed or not configured");
  }
}

void syncTime() {
  if (WiFi.status() != WL_CONNECTED) return;
  configTime(0, 0, "pool.ntp.org");
  Serial.println("Syncing time...");
  time_t now = time(nullptr);
  unsigned long start = millis();
  while (now < 100000 && millis() - start < 8000) {
    delay(200);
    now = time(nullptr);
  }
  if (now >= 100000) Serial.println("Time synced");
}

String formattedTime() {
  time_t now = time(nullptr);
  struct tm timeinfo;
  if (!localtime_r(&now, &timeinfo)) return String("--:--");
  char buf[32];
  strftime(buf, sizeof(buf), "%H:%M:%S", &timeinfo);
  return String(buf);
}

// ---------- SAMPLE ACTIONS (start/stop timers via serial commands) ----------
// For testing: send commands over Serial (USB) to control features
// Commands: SW_START, SW_STOP, SW_RESET, POM_START, POM_STOP, REQ

void serialCommand(const String &cmd) {
  if (cmd == "SW_START") {
    swRunning = true; swStart = millis(); swElapsed = 0;
  } else if (cmd == "SW_STOP") {
    swRunning = false; swElapsed = millis() - swStart;
  } else if (cmd == "SW_RESET") {
    swRunning = false; swElapsed = 0;
  } else if (cmd == "POM_START") {
    pomRunning = true; pomOnBreak = false; pomStart = millis();
  } else if (cmd == "POM_STOP") {
    pomRunning = false; pomOnBreak = false;
  }
}

// Monitor USB Serial for local control commands
void serialEvent() {
  while (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length()>0) serialCommand(line);
  }
}

/* End of esp32_mimobot.ino */
