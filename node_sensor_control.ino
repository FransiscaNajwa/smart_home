#include <painlessMesh.h>
#include <ArduinoJson.h>
#include <NTPClient.h>
#include <WiFiUdp.h>

#define MESH_PREFIX "SmartHomeMesh"
#define MESH_PASSWORD "mesh_jarkom_123"
#define MESH_PORT 5555

painlessMesh mesh;
#define MOTOR_PIN 5     // I/O5 untuk kontrol kipas via relay
#define ACS712_PIN A0   // ADC pin untuk sensor arus

Scheduler userScheduler;
Task sensorDataTask(10000, TASK_FOREVER, &sendSensorData);

// NTP Configuration
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", 25200, 60000); // WIB = UTC+7

// Fungsi untuk membaca arus dari ACS712 dengan filter
float readCurrent() {
  const int samples = 10;
  float total = 0;
  for (int i = 0; i < samples; i++) {
    int rawValue = analogRead(ACS712_PIN);
    if (rawValue < 0 || rawValue > 1023) return -1; // Error detection
    float voltage = (rawValue / 1023.0) * 5.0;
    float current = (voltage - 2.5) / 0.066;
    total += current > 0 ? current : 0;
    delay(10);
  }
  float avgCurrent = total / samples;
  return avgCurrent > 0.01 ? avgCurrent : 0; // Minimum threshold 0.01A
}

void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Received from Mesh node %u: %s\n", from, msg.c_str());
  DynamicJsonDocument doc(128); // Reduced size for ESP8266
  DeserializationError error = deserializeJson(doc, msg);
  if (error) {
    Serial.println("deserializeJson() failed");
    return;
  }
  String device = doc["device"];
  String state = doc["state"];
  if (device == "kipas") {
    digitalWrite(MOTOR_PIN, state == "ON" ? LOW : HIGH);
    Serial.println(state == "ON" ? "KIPAS DINYALAKAN" : "KIPAS DIMATIKAN");
  }
}

void sendSensorData() {
  float current = readCurrent();
  if (current < 0) {
    Serial.println("Error reading ACS712");
    return;
  }
  float watt = 5.0 * current;
  timeClient.update();
  String timestamp = timeClient.getFormattedTime();
  DynamicJsonDocument doc(128);
  doc["device"] = "kipas";
  doc["status"] = digitalRead(MOTOR_PIN) == LOW ? "ON" : "OFF";
  doc["current"] = current;
  doc["watt"] = watt;
  doc["timestamp"] = timestamp;

  String msg;
  serializeJson(doc, msg);
  mesh.sendBroadcast(msg);
  Serial.println("Terkirim via Mesh: " + msg);
}

void setup() {
  Serial.begin(115200);
  pinMode(MOTOR_PIN, OUTPUT);
  digitalWrite(MOTOR_PIN, HIGH); // Matikan awalnya
  timeClient.begin();
  mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  mesh.onReceive(&receivedCallback);
  userScheduler.addTask(sensorDataTask);
  sensorDataTask.enable();
  sendSensorData();
}

void loop() {
  mesh.update();
}