#include <painlessMesh.h>
#include <Wire.h>
#include <BH1750.h>
#include <ArduinoJson.h> // Tambahkan ini untuk parsing JSON

// Mesh config
#define   MESH_PREFIX     "SmartHomeMesh"
#define   MESH_PASSWORD   "meshpassword"
#define   MESH_PORT       5555

// Pin untuk LED/Relay lampu (contoh: GPIO 2)
#define LED_PIN 2 // <--- PENTING: GANTI DENGAN PIN GPIO YANG BENAR UNTUK LED/RELAY ANDA

Scheduler userScheduler;
painlessMesh mesh;

BH1750 lightMeter;
String nodeName = "lampu";

// --- PROTOTIPE FUNGSI ---
// Deklarasikan fungsi di sini agar kompilator tahu mereka ada
void sendLightData();
void receivedCallback(uint32_t from, String &msg);

// Deklarasi Task secara global
Task lightSensorTask(5000, TASK_FOREVER, &sendLightData);


// Fungsi kirim data ke root
void sendLightData() {
  float lux = lightMeter.readLightLevel();
  
  String msg = "{";
  msg += "\"node\":\"" + nodeName + "\",";
  msg += "\"lux\":" + String(lux, 2);
  msg += "}";

  mesh.sendBroadcast(msg);
  Serial.println("Terkirim: " + msg);
}

// Fungsi terima pesan dari root node (dalam format JSON)
void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Dari %u: %s\n", from, msg.c_str());

  DynamicJsonDocument doc(256); // Ukuran disesuaikan dengan kebutuhan payload
  DeserializationError error = deserializeJson(doc, msg);

  if (error) {
    Serial.print("deserializeJson() failed: ");
    Serial.println(error.c_str());
    return;
  }

  String device = doc["device"];
  String state = doc["state"];

  if (device == "lampu") { // Pastikan ini menargetkan device "lampu"
    if (state == "ON") {
      digitalWrite(LED_PIN, HIGH);
      Serial.println("LAMPU DINYALAKAN");
    } else if (state == "OFF") {
      digitalWrite(LED_PIN, LOW);
      Serial.println("LAMPU DIMATIKAN");
    }
  }
}

void setup() {
  Serial.begin(115200);

  // Inisialisasi BH1750
  Wire.begin(21, 22); // SDA, SCL. Pastikan ini adalah pin I2C yang benar untuk ESP32 Anda
  lightMeter.begin();

  // Inisialisasi pin LED/Relay
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW); // Pastikan lampu mati di awal

  // Inisialisasi mesh
  mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  mesh.onReceive(&receivedCallback);
  
  // Jadwal kirim data setiap 5 detik
  userScheduler.addTask(lightSensorTask); // Tambahkan task yang sudah dideklarasikan
  lightSensorTask.enable();             // Aktifkan task
  sendLightData();                      // kirim langsung pertama kali
}

void loop() {
  mesh.update();
}