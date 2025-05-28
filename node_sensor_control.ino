#include <painlessMesh.h>
#include <Wire.h>      // Untuk sensor BH1750
#include <BH1750.h>    // Untuk sensor cahaya
#include <DHT.h>       // Untuk sensor suhu/kelembaban
#include <ArduinoJson.h> // Untuk parsing dan serialisasi JSON

// Mesh config (harus sama dengan root node dan node lainnya)
#define   MESH_PREFIX     "SmartHomeMesh"
#define   MESH_PASSWORD   "meshpassword"
#define   MESH_PORT       5555

// --- DEFINISI PIN UNTUK KEDUA PERANGKAT ---
#define LED_PIN 2       // <--- GANTI DENGAN PIN GPIO YANG TERHUBUNG KE LED/RELAY LAMPU ANDA
#define DHTPIN 4        // <--- GANTI DENGAN PIN GPIO YANG BENAR UNTUK DHT11 ANDA
#define DHTTYPE DHT11
#define MOTOR_PIN 15    // <--- GANTI DENGAN PIN GPIO YANG TERHUBUNG KE DRIVER MOTOR KIPAS ANDA

// Deklarasi objek sensor
BH1750 lightMeter;
DHT dht(DHTPIN, DHTTYPE);

Scheduler userScheduler;
painlessMesh mesh;

// Nama node ini, akan muncul di payload JSON
String nodeName = "sensor_control_node";

// --- PROTOTIPE FUNGSI ---
// Deklarasikan fungsi di sini agar kompilator tahu mereka ada
void sendAllSensorData();
void receivedCallback(uint32_t from, String &msg);

// Deklarasi Task global untuk pengiriman data sensor (setiap 5 detik)
Task allSensorDataTask(5000, TASK_FOREVER, &sendAllSensorData);

// Fungsi untuk membaca semua sensor dan mengirim data gabungan ke root
void sendAllSensorData() {
  float lux = lightMeter.readLightLevel();
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  // Penanganan pembacaan sensor yang gagal
  if (isnan(h) || isnan(t)) {
    Serial.println("Gagal membaca dari sensor DHT");
    // Anda mungkin ingin mengirim nilai default atau null jika gagal
    h = -1.0; // Contoh: kirim -1 sebagai indikasi gagal
    t = -1.0;
  }
  if (lux < 0) { // BH1750 mengembalikan -1 jika gagal membaca
    Serial.println("Gagal membaca dari sensor BH1750");
    lux = -1.0; // Contoh: kirim -1 sebagai indikasi gagal
  }

  // Buat payload JSON gabungan
  String msg = "{";
  msg += "\"node\":\"" + nodeName + "\",";
  msg += "\"lux\":" + String(lux, 2) + ",";
  msg += "\"temperature\":" + String(t, 1) + ",";
  msg += "\"humidity\":" + String(h, 1);
  msg += "}";

  mesh.sendBroadcast(msg);
  Serial.println("Terkirim: " + msg);
}

// Fungsi untuk menerima pesan kontrol dari root node (melalui mesh)
void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Pesan dari %u: %s\n", from, msg.c_str());

  DynamicJsonDocument doc(256); // Ukuran disesuaikan dengan payload kontrol
  DeserializationError error = deserializeJson(doc, msg);

  if (error) {
    Serial.print("deserializeJson() failed: ");
    Serial.println(error.c_str());
    return;
  }

  String device = doc["device"]; // Ambil nama perangkat (misal: "lampu" atau "kipas")
  String state = doc["state"];   // Ambil status (misal: "ON" atau "OFF")

  // Logika kontrol untuk lampu
  if (device == "lampu") {
    if (state == "ON") {
      digitalWrite(LED_PIN, HIGH);
      Serial.println("LAMPU DINYALAKAN");
    } else if (state == "OFF") {
      digitalWrite(LED_PIN, LOW);
      Serial.println("LAMPU DIMATIKAN");
    }
  }
  // Logika kontrol untuk kipas
  else if (device == "kipas") {
    if (state == "ON") {
      digitalWrite(MOTOR_PIN, HIGH);
      Serial.println("KIPAS DINYALAKAN");
    } else if (state == "OFF") {
      digitalWrite(MOTOR_PIN, LOW);
      Serial.println("KIPAS DIMATIKAN");
    }
  }
}

void setup() {
  Serial.begin(115200);

  // Inisialisasi sensor BH1750 (I2C)
  // Pastikan pin SDA/SCL ini benar untuk ESP32 Anda
  Wire.begin(21, 22);
  lightMeter.begin();

  // Inisialisasi sensor DHT
  dht.begin();

  // Inisialisasi pin aktuator (LED untuk lampu, MOTOR_PIN untuk kipas)
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW); // Pastikan lampu mati di awal

  pinMode(MOTOR_PIN, OUTPUT);
  digitalWrite(MOTOR_PIN, LOW); // Pastikan kipas mati di awal

  // Inisialisasi mesh
  mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  mesh.onReceive(&receivedCallback);
  
  // Tambahkan task untuk mengirim data gabungan setiap 5 detik
  userScheduler.addTask(allSensorDataTask);
  allSensorDataTask.enable();
  sendAllSensorData(); // Kirim data langsung pertama kali saat startup
}

void loop() {
  mesh.update();
}