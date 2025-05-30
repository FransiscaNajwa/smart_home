#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <PainlessMesh.h>
#include <WiFiClientSecure.h>

// PainlessMesh Configuration
#define MESH_PREFIX "smart_home_mesh"
#define MESH_PASSWORD "mesh_password"
#define MESH_PORT 5555

// WiFi Configuration
const char* ssid = "your_wifi_ssid"; // Ganti dengan SSID WiFi Anda
const char* password = "your_wifi_password"; // Ganti dengan password WiFi Anda

// MQTT Configuration
const char* mqtt_server = "f6edeb4adb7c402ca.s1.eu.hivemq.cloud";
const int mqtt_port = 8883;
const char* mqtt_user = "hivemq.webclient.1747043357213";
const char* mqtt_password = "ab45PjNdISi;Bf9>2,G#";
const char* sensor_topic = "starswechase/sungai/data";
const char* control_topic = "starswechase/sungai/control";

// Sertifikat TLS (Let’s Encrypt)
const char* ca_cert = \
"-----BEGIN CERTIFICATE-----\n" \
"MIIDrzCCApegAwIBAgIQCDvgVpBCRrGhdWrJWZHHSjANBgkqhkiG9w0BAQUFADBh\n" \
"...(isi dengan konten letsencrypt.pem)...\n" \
"-----END CERTIFICATE-----\n";

// Pin untuk LED (Aktuator ESP32)
#define LED_PIN 2 // Ganti dengan pin yang sesuai untuk LED Anda

WiFiClientSecure espClient;
PubSubClient client(espClient);
PainlessMesh mesh;

// Fungsi untuk mendapatkan epoch time dalam milidetik
unsigned long getEpochTime() {
  time_t now;
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("Failed to obtain time");
    return 0;
  }
  time(&now);
  return (unsigned long)now * 1000; // Konversi ke milidetik
}

void setup() {
  Serial.begin(115200);
  
  // Inisialisasi LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Koneksi WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");

  // Sinkronisasi waktu untuk epoch time
  configTime(7 * 3600, 0, "pool.ntp.org"); // GMT+7 untuk WIB
  Serial.println("Waiting for time sync...");
  delay(2000);

  // Setup TLS dan MQTT
  espClient.setCACert(ca_cert);
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);

  // Inisialisasi PainlessMesh
  mesh.init(MESH_PREFIX, MESH_PASSWORD, MESH_PORT);
  mesh.onReceive(&receivedCallback);
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println("Message received on topic: " + String(topic));
  Serial.println("Payload: " + message);

  // Parsing pesan kontrol
  DynamicJsonDocument doc(256);
  deserializeJson(doc, message);
  if (String(topic) == control_topic && doc["device"] == "ESP32" && doc["actuator"] == "LED") {
    bool state = doc["state"];
    digitalWrite(LED_PIN, state ? HIGH : LOW);
    Serial.println("LED set to: " + String(state ? "ON" : "OFF"));
  }
}

void receivedCallback(uint32_t from, String &msg) {
  Serial.println("Received message from mesh node: " + msg);
  
  // Parsing pesan dari ESP8266
  DynamicJsonDocument doc(256);
  deserializeJson(doc, msg);
  String payload;
  serializeJson(doc, payload);
  
  // Kirim ke MQTT
  if (client.connected()) {
    client.publish(sensor_topic, payload.c_str());
    Serial.println("Published to MQTT: " + payload);
  } else {
    Serial.println("MQTT not connected, cannot publish");
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.println("Attempting MQTT connection...");
    String clientId = "ESP32Client-" + String(random(0xffff), HEX);
    if (client.connect(clientId.c_str(), mqtt_user, mqtt_password)) {
      Serial.println("Connected to MQTT");
      client.subscribe(control_topic);
    } else {
      Serial.print("Failed, rc=");
      Serial.print(client.state());
      Serial.println(" Retrying in 5 seconds...");
      delay(5000);
    }
  }
}

void loop() {
  mesh.update();
  
  // Pastikan MQTT terhubung
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Baca data sensor (LUX) - Untuk simulasi, gunakan random
  float lux = random(400, 600) / 1.0; // Ganti dengan pembacaan sensor LUX
  float voltage = 3.0 + (random(0, 4) / 10.0);

  // Buat payload JSON
  DynamicJsonDocument doc(256);
  doc["device"] = "ESP32";
  doc["lux"] = lux;
  doc["voltage"] = voltage;
  doc["actuator"] = "LED";
  doc["actuator_state"] = digitalRead(LED_PIN);
  doc["timestamp"] = getEpochTime();
  
  String payload;
  serializeJson(doc, payload);

  // Kirim ke MQTT
  if (client.connected()) {
    client.publish(sensor_topic, payload.c_str());
    Serial.println("Published ESP32 data to MQTT: " + payload);
  } else {
    Serial.println("MQTT not connected, cannot publish ESP32 data");
  }

  delay(5000); // Kirim data setiap 5 detik
}