#include <ESP8266WiFi.h> // Library WiFi untuk ESP8266
#include <painlessMesh.h>   // Library untuk Mesh Networking
#include <ArduinoJson.h>    // Library untuk JSON
#include <DHT.h>            // Library untuk sensor DHT (jika Anda pakai DHT11/DHT22)
#include <Adafruit_Sensor.h> // Library dasar untuk sensor Adafruit (diperlukan DHT library)

// --- KONFIGURASI MESH (painlessMesh) ---
// HARUS SAMA PERSIS dengan konfigurasi di ESP32 Gateway Anda!
#define   MESH_PREFIX     "SmartHomeMesh"     // Nama Jaringan Mesh Anda
#define   MESH_PASSWORD   "mesh_jarkom_123"   // Kata Sandi Jaringan Mesh Anda
#define   MESH_PORT       5555                // Port untuk komunikasi Mesh

painlessMesh  mesh; // Objek painlessMesh

// --- KONFIGURASI SENSOR (Contoh DHT11/DHT22) ---
// Ganti dengan pin GPIO yang DATA pin DHT Anda terhubung di NodeMCU.
// Perhatikan: Pin D2 pada NodeMCU adalah GPIO4. Sesuaikan jika Anda pakai pin lain.
#define DHTPIN D2          // Pin GPIO tempat DATA pin DHT terhubung (contoh GPIO4)
#define DHTTYPE DHT11      // Ganti DHT11 atau DHT22 sesuai sensor Anda
DHT dht(DHTPIN, DHTTYPE);  // Inisialisasi sensor DHT

// --- PIN UNTUK AKTUATOR (Contoh: LED eksternal atau Relay untuk Lampu) ---
// Ganti dengan pin GPIO yang terhubung ke lampu atau aktuator lain di NodeMCU.
// Pin D1 pada NodeMCU adalah GPIO5. Sesuaikan jika Anda pakai pin lain.
const int LAMP_PIN = D1; // Pin GPIO untuk lampu yang dikontrol oleh NodeMCU ini (misalnya D1/GPIO5)
// const int FAN_PIN = DX; // Contoh: Pin untuk kipas, jika ada

// Variabel untuk melacak waktu pengiriman data sensor
unsigned long lastSensorReadMillis = 0;
const long sensorReadInterval = 15000; // Baca dan kirim data sensor setiap 15 detik

// --- MESH CALLBACKS ---
// Dipanggil saat NodeMCU ini menerima pesan dari node Mesh lain (termasuk Gateway)
void receivedCallback( uint32_t from, String &msg ) {
  Serial.printf("NodeMCU received from Mesh node %u: %s\n", from, msg.c_str());

  // ASUMSI: 'msg' adalah perintah kontrol dari Gateway (yang berasal dari Flask via MQTT).
  // Misalnya: "{\"device\":\"lampu\",\"command\":\"ON\"}"
  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, msg);

  if (error) {
    Serial.print(F("deserializeJson() failed: "));
    Serial.println(error.f_str());
    return;
  }

  String device = doc["device"].as<String>();
  String command = doc["command"].as<String>();

  Serial.printf("Parsed command: Device=%s, Command=%s\n", device.c_str(), command.c_str());

  // --- LOGIKA KONTROL AKTUATOR LOKAL DI NODEMCU INI ---
  if (device == "lampu") {
    if (command == "ON") {
      digitalWrite(LAMP_PIN, HIGH);
      Serial.println("Lamp ON (controlled by this NodeMCU)");
    } else if (command == "OFF") {
      digitalWrite(LAMP_PIN, LOW);
      Serial.println("Lamp OFF (controlled by this NodeMCU)");
    }
  }
  // Tambahkan logika untuk kipas, dll. jika ada
  else if (device == "kipas") {
    Serial.print("Control message for Fan: ");
    Serial.println(command);
    // if (command == "HIGH") { ... }
    // else if (command == "OFF") { ... }
  }
}

// Dipanggil saat NodeMCU ini berhasil terhubung ke jaringan Mesh
void newConnectionCallback(uint32_t nodeId) {
    Serial.printf("New connection in Mesh: %u\n", nodeId);
}

// Dipanggil saat koneksi Mesh berubah (node bergabung/meninggalkan)
void changedConnectionsCallback() {
    Serial.printf("Changed connections. Total nodes: %d\n", mesh.getNodeList().size());
}

// Dipanggil saat Mesh menemukan node baru dan menyesuaikan waktu
void nodeTimeAdjustedCallback(int32_t offset) {
    Serial.printf("Adjusted time %u. Offset = %d\n", mesh.getNodeTime(), offset);
}

// --- SETUP UTAMA (Jalankan sekali saat NodeMCU pertama kali menyala) ---
void setup() {
  Serial.begin(115200); // Inisialisasi Serial Monitor
  pinMode(LAMP_PIN, OUTPUT); // Inisialisasi pin untuk lampu

  // Inisialisasi sensor DHT
  dht.begin();
  Serial.println("DHT sensor initialized.");

  // 1. Setup painlessMesh
  // mesh.setDebugMsgLevel( (MeshDebug)LOG_ERROR ); // Hanya tampilkan error untuk debugging Mesh
  mesh.init( MESH_PREFIX, MESH_PASSWORD, MESH_PORT );
  mesh.onReceive(&receivedCallback);          // Callback saat pesan diterima dari Mesh
  mesh.onNewConnection(&newConnectionCallback); // Callback saat ada node baru terhubung
  mesh.onChangedConnections(&changedConnectionsCallback); // Callback saat koneksi berubah
  mesh.onNodeTimeAdjusted(&nodeTimeAdjustedCallback); // Callback saat waktu node disesuaikan

  // Node sensor ini BUKAN root, jadi JANGAN panggil mesh.setContainsRoot(true);
}

// --- LOOP UTAMA (Jalankan terus menerus setelah setup) ---
void loop() {
  // Penting: Panggil mesh.update() di awal loop untuk menjaga jaringan Mesh
  mesh.update();

  unsigned long currentMillis = millis();
  if (currentMillis - lastSensorReadMillis > sensorReadInterval) {
    lastSensorReadMillis = currentMillis;

    // --- BACA DATA SENSOR ---
    float h = dht.readHumidity();
    float t = dht.readTemperature();

    // Periksa apakah pembacaan gagal
    if (isnan(h) || isnan(t)) {
      Serial.println("Failed to read from DHT sensor!");
      // Jangan kirim data jika pembacaan gagal
      return;
    }

    // --- BUAT PAYLOAD JSON UNTUK DATA SENSOR ---
    StaticJsonDocument<200> doc; // Ukuran dokumen JSON, sesuaikan jika perlu
    doc["temperature"] = t;
    doc["humidity"] = h;
    doc["device_id"] = mesh.getNodeId(); // Kirim ID NodeMesh ini
    doc["type"] = "sensor_data"; // Tambahkan tipe data agar Gateway bisa membedakan

    char jsonBuffer[200];
    serializeJson(doc, jsonBuffer); // Serialize JSON ke string

    Serial.print("Publishing sensor data to Mesh: ");
    Serial.println(jsonBuffer);

    // --- PUBLIKASIKAN PESAN SENSOR KE MESH (ke Gateway) ---
    // Karena Gateway adalah root, dan kita ingin semua data sensor ke sana,
    // kita bisa menggunakan sendBroadcast dan Gateway akan menerimanya di receivedCallback-nya.
    // Atau jika Anda tahu ID Gateway, bisa pakai mesh.sendSingle(GATEWAY_NODE_ID, jsonBuffer);
    mesh.sendBroadcast(jsonBuffer);
  }
}