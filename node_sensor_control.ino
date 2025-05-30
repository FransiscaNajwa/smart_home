#include <ESP8266WiFi.h>
#include <PainlessMesh.h>
#include <ArduinoJson.h>

// PainlessMesh Configuration
#define MESH_PREFIX "smart_home_mesh"
#define MESH_PASSWORD "mesh_password"
#define MESH_PORT 5555

// Pin untuk Motor (Aktuator ESP8266)
#define MOTOR_PIN D1 // Ganti dengan pin yang sesuai untuk motor Anda

PainlessMesh mesh;

// Fungsi untuk mendapatkan epoch time dalam milidetik (opsional, jika diperlukan)
unsigned long getEpochTime() {
  return millis(); // Untuk ESP8266, gunakan millis() sebagai simulasi
}

void setup() {
  Serial.begin(115200);

  // Inisialisasi motor
  pinMode(MOTOR_PIN, OUTPUT);
  digitalWrite(MOTOR_PIN, LOW);

  // Inisialisasi PainlessMesh
  mesh.init(MESH_PREFIX, MESH_PASSWORD, MESH_PORT);
  mesh.onReceive(&receivedCallback);
}

void receivedCallback(uint32_t from, String &msg) {
  Serial.println("Received control message from mesh: " + msg);

  // Parsing pesan kontrol
  DynamicJsonDocument doc(256);
  deserializeJson(doc, msg);
  if (doc["device"] == "ESP8266" && doc["actuator"] == "MOTOR") {
    bool state = doc["state"];
    digitalWrite(MOTOR_PIN, state ? HIGH : LOW);
    Serial.println("Motor set to: " + String(state ? "ON" : "OFF"));
  }
}

void loop() {
  mesh.update();

  // Baca data sensor (Suhu dan Kelembapan) - Untuk simulasi, gunakan random
  float temperature = random(240, 270) / 10.0; // Ganti dengan pembacaan sensor (misalnya, DHT11)
  float humidity = random(550, 650) / 10.0; // Ganti dengan pembacaan sensor
  float voltage = 3.0 + (random(0, 4) / 10.0);

  // Buat payload JSON
  DynamicJsonDocument doc(256);
  doc["device"] = "ESP8266";
  doc["temperature"] = temperature;
  doc["humidity"] = humidity;
  doc["voltage"] = voltage;
  doc["actuator"] = "MOTOR";
  doc["actuator_state"] = digitalRead(MOTOR_PIN);
  doc["timestamp"] = getEpochTime();

  String payload;
  serializeJson(doc, payload);

  // Kirim ke ESP32 melalui mesh
  mesh.sendBroadcast(payload);
  Serial.println("Sent ESP8266 data to mesh: " + payload);

  delay(5000); // Kirim data setiap 5 detik
}