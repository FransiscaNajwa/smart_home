#include <painlessMesh.h>   // Library untuk Mesh Networking
#include <ArduinoJson.h>    // Library untuk JSON
#include <DHT.h>            // Untuk sensor suhu/kelembaban

// --- KONFIGURASI MESH ---
#define MESH_PREFIX "SmartHomeMesh"
#define MESH_PASSWORD "mesh_jarkom_123"
#define MESH_PORT 5555

painlessMesh mesh;

// --- DEFINISI PIN UNTUK NODE ---
#define DHTPIN 4        // Pin untuk DHT11 (D2 pada NodeMCU)
#define DHTTYPE DHT11
#define MOTOR_PIN 15    // Pin untuk motor (kipas) (D8 pada NodeMCU)

// Objek sensor
DHT dht(DHTPIN, DHTTYPE);

// Variabel untuk Task dan interval
Scheduler userScheduler;
Task allSensorDataTask(10000, TASK_FOREVER, &sendAllSensorData); // 10 detik untuk Node

// --- MESH CALLBACKS ---
void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Received from Mesh node %u: %s\n", from, msg.c_str());

  // Node memproses pesan kontrol dari Gateway
  DynamicJsonDocument doc(256);
  DeserializationError error = deserializeJson(doc, msg);
  if (error) {
    Serial.print("deserializeJson() failed: ");
    Serial.println(error.c_str());
    return;
  }

  String device = doc["device"];
  String state = doc["state"];

  if (device == "kipas") {
    digitalWrite(MOTOR_PIN, state == "ON" ? HIGH : LOW);
    Serial.println(state == "ON" ? "KIPAS DINYALAKAN" : "KIPAS DIMATIKAN");
  }
}

// --- FUNGSI NODE (Mengirim Data Sensor) ---
void sendAllSensorData() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("Gagal membaca dari sensor DHT, melewatkan pengiriman.");
    return; // Melewatkan pengiriman jika ada data tidak valid
  }

  DynamicJsonDocument doc(128);
  doc["device"] = "ESP8266"; // Menambahkan identifikasi device
  doc["temperature"] = t;
  doc["humidity"] = h;
  doc["actuator_state"] = digitalRead(MOTOR_PIN) == HIGH; // Status kipas

  String msg;
  serializeJson(doc, msg);
  mesh.sendBroadcast(msg);
  Serial.println("Terkirim: " + msg);
}

// --- SETUP UTAMA ---
void setup() {
  Serial.begin(115200);

  // Inisialisasi sensor untuk Node
  dht.begin();
  pinMode(MOTOR_PIN, OUTPUT);
  digitalWrite(MOTOR_PIN, LOW);

  // Inisialisasi Mesh untuk Node
  mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  mesh.onReceive(&receivedCallback);
  userScheduler.addTask(allSensorDataTask);
  allSensorDataTask.enable();
  sendAllSensorData(); // Kirim data pertama kali
}

// --- LOOP UTAMA ---
void loop() {
  mesh.update();
}