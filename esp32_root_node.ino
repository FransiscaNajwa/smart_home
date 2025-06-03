#include <painlessMesh.h>   // Library untuk Mesh Networking
#include <ArduinoJson.h>    // Library untuk JSON

// --- KONFIGURASI MESH ---
#define MESH_PREFIX "SmartHomeMesh"
#define MESH_PASSWORD "mesh_jarkom_123"
#define MESH_PORT 5555

painlessMesh mesh;

// --- DEFINISI PIN UNTUK NODE ---
#define LED_PIN 2       // Pin untuk LED (lampu)

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

  if (device == "lampu") {
    digitalWrite(LED_PIN, state == "ON" ? HIGH : LOW);
    Serial.println(state == "ON" ? "LAMPU DINYALAKAN" : "LAMPU DIMATIKAN");
  }
}

// --- FUNGSI NODE (Mengirim Data Dummy) ---
void sendAllSensorData() {
  DynamicJsonDocument doc(128);
  doc["device"] = "ESP32"; // Identifikasi device
  doc["lux"] = 0; // Data dummy karena BH1750 tidak terhubung
  doc["actuator_state"] = digitalRead(LED_PIN) == HIGH; // Status lampu

  String msg;
  serializeJson(doc, msg);
  mesh.sendBroadcast(msg);
  Serial.println("Terkirim: " + msg);
}

// --- SETUP UTAMA ---
void setup() {
  Serial.begin(115200);

  // Inisialisasi pin untuk Node
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

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