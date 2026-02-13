/*
  atmega_sensors.ino
  Firmware for ATmega328P (Arduino Uno/Nano) - Sensor Controller for MIMOBOT

  Responsibilities (sensor-only):
  - Read DHT11/DHT22 temperature sensor
  - Read Ultrasonic HC-SR04 or IR proximity sensor
  - Read LDR via analog input with 10k resistor divider
  - Send periodic sensor data to ESP32 over UART in simple text format

  Notes:
  - Minimal delays; uses non-blocking patterns where practical
  - Defaults: DHT on digital pin 2, TRIG/ECHO on pins for HC-SR04
  - If HC-SR04 not present, an IR proximity stub can be used
*/

#include <DHT.h>

// ---------- CONFIG ----------
#define BAUD 115200

// DHT
#define DHTPIN 2
#define DHTTYPE DHT22 // change to DHT11 if using that sensor
DHT dht(DHTPIN, DHTTYPE);

// Ultrasonic HC-SR04 (or IR alternative)
#define TRIG_PIN 8
#define ECHO_PIN 7

// LDR
#define LDR_PIN A0

// Timing
unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 3000; // ms

// For ultrasonic non-blocking echo timing
unsigned long echoStart = 0;
bool expectingEcho = false;

void setup() {
  Serial.begin(BAUD);
  dht.begin();

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  pinMode(LDR_PIN, INPUT);

  // small startup message
  Serial.println("ATMEGA Sensors Ready");
}

void loop() {
  unsigned long now = millis();

  // Non-blocking: send sensor data periodically
  if (now - lastSend >= SEND_INTERVAL) {
    lastSend = now;
    sendSensorData();
  }

  // Minimal other processing - allow DHT timing via library
}

void sendSensorData() {
  // Read temperature
  float t = dht.readTemperature();
  if (isnan(t)) {
    // if reading failed, send a placeholder
    Serial.println("TEMP:NaN");
  } else {
    // send with one decimal
    char buf[32];
    dtostrf(t, 4, 1, buf);
    Serial.print("TEMP:"); Serial.println(buf);
  }

  // Read LDR and categorize
  int ldr = analogRead(LDR_PIN);
  // Simplified thresholds (calibrate for environment)
  String lightState = "UNKNOWN";
  if (ldr > 800) lightState = "BRIGHT";
  else if (ldr > 400) lightState = "NORMAL";
  else lightState = "DIM";
  Serial.print("LIGHT:"); Serial.println(lightState);

  // Ultrasonic distance
  long duration, distanceCm;
  // send 10us pulse to trigger
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  duration = pulseIn(ECHO_PIN, HIGH, 20000); // timeout 20ms
  if (duration == 0) {
    // no echo
    Serial.println("PROX:UNKNOWN");
  } else {
    distanceCm = duration / 58; // approximate
    if (distanceCm < 20) Serial.println("PROX:USER_PRESENT");
    else Serial.println("PROX:EMPTY");
  }

  // Sample UART output summary for debugging
  Serial.println("--END--");
}

/* Example UART output (ESP32 should parse lines):
ATMEGA Sensors Ready
TEMP:24.5
LIGHT:BRIGHT
PROX:USER_PRESENT
--END--
*/
