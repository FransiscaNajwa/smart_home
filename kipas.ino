#include <painlessMesh.h>
#include <DHT.h>
#include <ArduinoJson.h> // Tambahkan ini untuk parsing JSON

#define DHTPIN 4      // <--- PENTING: GANTI DENGAN PIN GPIO YANG BENAR UNTUK DHT11 ANDA
#define DHTTYPE DHT11
#define MOTOR_PIN 15  // Pin motor DC (ubah sesuai wiring)

DHT dht(DHTPIN, DHTTYPE);

// Mesh Configuration
#define   MESH_PREFIX     "SmartHomeMesh"
#define   MESH_PASSWORD   "meshpassword"
#define   MESH_PORT       5555

Scheduler userScheduler;
painlessMesh mesh;

String nodeName = "kipas";

// --- PROTOTIPE FUNGSI ---
// Deklarasikan fungsi di sini agar kompilator tahu mereka ada
void sendDHTData();
void receivedCallback(uint32_t from, String &msg);

// Deklarasi Task secara global agar bisa ditambahkan ke scheduler
// Sekarang sendDHTData sudah dideklarasikan melalui prototipe di atas
Task dhtSensorTask(5000, TASK_FOREVER, &sendDHTData);


// Fungsi kirim suhu dan kelembapan
void sendDHTData() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("Gagal membaca dari sensor DHT");
    return;
  }

  String msg = "{";
  msg += "\"node\":\"" + nodeName + "\",";
  msg += "\"temperature\":" + String(t, 1) + ",";
  msg += "\"humidity\":" + String(h, 1);
  msg += "}";

  mesh.sendBroadcast(msg);
  Serial.println("Terkirim: " + msg);
}

// Terima pesan dari root node (dalam format JSON)
void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Pesan dari %u: %s\n", from, msg.c_str());

  DynamicJsonDocument doc(256); // Ukuran disesuaikan dengan kebutuhan payload
  DeserializationError error = deserializeJson(doc, msg);

  if (error) {
    Serial.print("deserializeJson() failed: ");
    Serial.println(error.c_str());
    return;
  }

  String device = doc["device"];
  String state = doc["state"];

  if (device == "kipas") { // Pastikan ini menargetkan device "kipas"
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
  dht.begin();
  pinMode(MOTOR_PIN, OUTPUT);
  digitalWrite(MOTOR_PIN, LOW); // Awal: kipas mati

  mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  mesh.onReceive(&receivedCallback);

  userScheduler.addTask(dhtSensorTask); // Tambahkan task yang sudah dideklarasikan
  dhtSensorTask.enable();              // Aktifkan task
  sendDHTData();                       // kirim langsung pertama kali
}

void loop() {
  mesh.update();
}