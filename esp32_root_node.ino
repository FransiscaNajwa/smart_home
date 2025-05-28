#include <painlessMesh.h>
#include <WiFi.h>
#include <PubSubClient.h>

// === WiFi dan MQTT Config ===
const char* ssid = ""; // Ganti dengan SSID WiFi Anda
const char* password = ""; // Ganti dengan password WiFi Anda

const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;

// --- PERBAIKAN PENTING DI SINI ---
// mqtt_topic_sub di root node (apa yang root node dengarkan dari MQTT broker)
// HARUS SAMA dengan mqtt_topic_pub di Flask (apa yang Flask kirimkan sebagai perintah kontrol)
const char* mqtt_topic_sub = "rumah/control"; // ROOT NODE MENDENGARKAN PERINTAH DARI FLASK

// mqtt_topic_pub di root node (apa yang root node kirimkan ke MQTT broker)
// HARUS SAMA dengan mqtt_topic_sub di Flask (apa yang Flask dengarkan sebagai data sensor)
const char* mqtt_topic_pub = "rumah/status"; // ROOT NODE MENGIRIM DATA SENSOR KE FLASK
// --- AKHIR PERBAIKAN PENTING ---

// === Mesh Config ===
#define MESH_PREFIX "SmartHomeMesh"
#define MESH_PASSWORD "meshpassword"
#define MESH_PORT 5555

Scheduler userScheduler;
painlessMesh mesh;

WiFiClient espClient;
PubSubClient client(espClient);

// MQTT reconnect
void reconnect() {
  while (!client.connected()) {
    Serial.print("Menghubungkan ke MQTT...");
    // Ganti "ESP32RootNode" dengan ID unik jika Anda memiliki beberapa root node
    if (client.connect("ESP32RootNode")) { 
      Serial.println("Terhubung!");
      // Setelah terhubung, berlangganan ke topik kontrol dari Flask
      client.subscribe(mqtt_topic_sub); 
      Serial.printf("Berlangganan ke topik MQTT: %s\n", mqtt_topic_sub);
    } else {
      Serial.print("Gagal, rc=");
      Serial.print(client.state());
      Serial.println(" coba lagi dalam 2 detik");
      delay(2000);
    }
  }
}

// Kirim data ke HiveMQ
void publishToMQTT(String payload) {
  // Pastikan klien MQTT terhubung sebelum mencoba memublikasikan
  if (client.connected()) {
    client.publish(mqtt_topic_pub, payload.c_str());
    Serial.println("Dikirim ke MQTT: " + payload);
  } else {
    Serial.println("Klien MQTT tidak terhubung, tidak dapat memublikasikan.");
  }
}

// Terima pesan dari MQTT (ON/OFF)
void callback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (unsigned int i = 0; i < length; i++) {
    msg += (char)payload[i];
  }

  Serial.printf("Pesan dari MQTT (topik: %s): %s\n", topic, msg.c_str());
  mesh.sendBroadcast(msg);  // teruskan ke node lewat mesh
  Serial.println("Pesan MQTT diteruskan ke Mesh.");
}

// Terima dari node mesh
void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Pesan dari node %u di Mesh: %s\n", from, msg.c_str());
  publishToMQTT(msg); // Publikasikan data dari mesh ke MQTT broker
}

void setup() {
  Serial.begin(115200);
  delay(100); // Sedikit delay untuk inisialisasi Serial

  Serial.println("\nMemulai Root Node ESP32...");

  // Wi-Fi
  Serial.printf("Menghubungkan ke WiFi: %s\n", ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print(".");
  }
  Serial.println("\nWiFi terhubung! IP Address: ");
  Serial.println(WiFi.localIP());

  // MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback); // Mengatur fungsi untuk menangani pesan MQTT yang masuk

  // Mesh
  Serial.println("Memulai PainlessMesh...");
  mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION); // Debug level
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  mesh.onReceive(&receivedCallback); // Mengatur fungsi untuk menangani pesan dari node mesh
  Serial.println("PainlessMesh diinisialisasi.");
}

void loop() {
  mesh.update(); // Update mesh network state

  // Pastikan klien MQTT terhubung
  if (!client.connected()) {
    reconnect();
  }
  client.loop(); // Memproses pesan masuk dan keluar untuk MQTT
}