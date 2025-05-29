#include <WiFi.h>
#include <PubSubClient.h>   // Library untuk MQTT
#include <ArduinoJson.h>    // Library untuk JSON (mengirim/menerima data terstruktur)
#include <painlessMesh.h>   // Library untuk Mesh Networking

// --- KONFIGURASI WIFI (Untuk Gateway terhubung ke Router) ---
// Ganti dengan NAMA WIFI dan PASSWORD Anda!
const char* ssid = "RESTU";
const char* password = "restu547";

// --- KONFIGURASI MQTT (Untuk Gateway terhubung ke HiveMQ Cloud) ---
// HOSTNAME dari HiveMQ Cloud Anda. Temukan ini di HiveMQ Cloud Dashboard > Cluster Details.
// Contoh: "f6edeb4adb7c402ca7291dd7ef4d8fc5.s1.eu.hivemq.cloud"
const char* mqtt_broker = "90c69dacebc2450495a401b6550d787b.s1.eu.hivemq.cloud"; // <-- GANTI DENGAN HOSTNAME ASLI ANDA!
const int mqtt_port = 8883; // Port SSL/TLS untuk HiveMQ Cloud
// Username dan Password MQTT yang Anda buat di HiveMQ Cloud untuk 'smarthome_iot_devices'
const char* mqtt_user = "smarthome_iot_devices";         // <-- GANTI DENGAN USERNAME ASLI ANDA!
const char* mqtt_password = "Smarthome99"; // <-- GANTI DENGAN PASSWORD ASLI ANDA!
const char* mqtt_client_id = "ESP32_Gateway_001";       // ID klien unik untuk Gateway ini. Harus unik di antara semua klien MQTT.

// --- KONFIGURASI TOPIK MQTT (sesuai dengan permissions di HiveMQ Cloud) ---
// Topik untuk Gateway mempublikasikan data sensor yang diterima dari Mesh ke Cloud
const char* mqtt_topic_publish_sensor = "starswechase/sungai/mesh_sensor_data";
// Topik untuk Gateway berlangganan perintah kontrol dari Cloud
const char* mqtt_topic_subscribe_control = "starswechase/sungai/control/#"; // Menggunakan '#' untuk semua sub-topik kontrol

// --- KONFIGURASI MESH (painlessMesh) ---
// Ganti dengan NAMA JARINGAN Mesh dan PASSWORD Mesh Anda!
// Ini harus sama di semua node Mesh Anda.
#define   MESH_PREFIX     "SmartHomeMesh"
#define   MESH_PASSWORD   "mesh_jarkom_123"
#define   MESH_PORT       5555 // Port untuk komunikasi Mesh

painlessMesh  mesh; // Objek painlessMesh

// --- PIN UNTUK AKTUATOR (Contoh: LED built-in ESP32) ---
// Sesuaikan dengan pin GPIO yang Anda gunakan untuk lampu atau aktuator lain.
const int LED_PIN = 2; // Pin GPIO untuk lampu LED (biasanya LED internal ESP32)

// Inisialisasi klien Wi-Fi dan MQTT
WiFiClient espClient;
PubSubClient client(espClient);

// Variabel untuk melacak waktu pengiriman data (contoh jika Gateway juga punya sensor, atau untuk keep-alive)
unsigned long lastPublishMillis = 0;
const long publishInterval = 30000; // Kirim pesan setiap 30 detik (contoh)

// --- MESH CALLBACKS ---
// Dipanggil saat Gateway menerima pesan dari node Mesh lain
void receivedCallback( uint32_t from, String &msg ) {
  Serial.printf("Gateway received from Mesh node %u: %s\n", from, msg.c_str());

  // ASUMSI: 'msg' adalah data sensor dari node Mesh dalam format JSON atau string sederhana.
  // Anda akan meneruskan pesan ini ke HiveMQ Cloud melalui MQTT.
  // Jika 'msg' perlu diproses (misal, ditambah timestamp), lakukan di sini.
  Serial.print("Publishing Mesh data to MQTT Cloud on topic: ");
  Serial.println(mqtt_topic_publish_sensor);
  client.publish(mqtt_topic_publish_sensor, msg.c_str());
}

// Dipanggil saat ada koneksi baru ke Mesh
void newConnectionCallback(uint32_t nodeId) {
    Serial.printf("New connection from Mesh node %u\n", nodeId);
}

// Dipanggil saat koneksi Mesh berubah (node bergabung/meninggalkan)
void changedConnectionsCallback() {
    Serial.printf("Changed connections. Total nodes: %d\n", mesh.getNodeList().size());
}

// Dipanggil saat Mesh menemukan node baru dan menyesuaikan waktu
void nodeTimeAdjustedCallback(int32_t offset) {
    Serial.printf("Adjusted time %u. Offset = %d\n", mesh.getNodeTime(), offset);
}

// --- MQTT CALLBACK ---
// Dipanggil saat pesan MQTT diterima dari HiveMQ Cloud
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived from Cloud on topic: ");
  Serial.println(topic);
  Serial.print("Payload: ");
  String messageTemp;
  for (int i = 0; i < length; i++) {
    Serial.print((char)payload[i]);
    messageTemp += (char)payload[i];
  }
  Serial.println();

  // --- LOGIKA KONTROL AKTUATOR LOKAL ATAU PENERUSAN PERINTAH KE MESH ---
  // Jika pesan diterima di topik kontrol lampu
  if (String(topic) == "starswechase/sungai/control/lampu") {
    Serial.print("Control message for Lamp: ");
    if (messageTemp == "ON") {
      digitalWrite(LED_PIN, HIGH); // Nyalakan LED (simulasi lampu di Gateway)
      Serial.println("LED ON");
      // Jika lampu adalah node Mesh terpisah, Anda akan meneruskan perintah ini ke Mesh
      // mesh.sendSingle(NODE_ID_LAMP_MESH, "ON"); // Ganti NODE_ID_LAMP_MESH dengan ID node lampu Anda
      // Atau broadcast ke semua node Mesh jika semua node memproses pesan kontrol:
      // mesh.sendBroadcast("{\"device\":\"lampu\",\"command\":\"ON\"}");
    } else if (messageTemp == "OFF") {
      digitalWrite(LED_PIN, LOW); // Matikan LED
      Serial.println("LED OFF");
      // Contoh: mesh.sendSingle(NODE_ID_LAMP_MESH, "OFF");
      // Atau broadcast:
      // mesh.sendBroadcast("{\"device\":\"lampu\",\"command\":\"OFF\"}");
    }
  }
  // Jika pesan diterima di topik kontrol kipas
  else if (String(topic) == "starswechase/sungai/control/kipas") {
    Serial.print("Control message for Fan: ");
    Serial.println(messageTemp);
    // Tambahkan logika kontrol kipas di sini, atau teruskan ke node Mesh yang mengontrol kipas
    // Contoh: mesh.sendSingle(NODE_ID_FAN_MESH, messageTemp);
    // Atau broadcast:
    // mesh.sendBroadcast("{\"device\":\"kipas\",\"command\":\"" + messageTemp + "\"}");
  }
  // Anda bisa menambahkan lebih banyak kondisi 'else if' untuk topik kontrol lainnya
}

// --- FUNGSI KONEKSI WIFI ---
void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    retries++;
    if(retries > 20){ // Coba 20 kali (10 detik), lalu restart ESP32
        Serial.println("\nFailed to connect to WiFi. Restarting ESP32...");
        ESP.restart();
    }
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

// --- FUNGSI REKONEKSI MQTT ---
void reconnect_mqtt() {
  // Loop sampai terhubung ke MQTT
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // client.setInsecure() memungkinkan koneksi TLS tanpa validasi sertifikat.
    // Ini bagus untuk development/testing, tapi TIDAK aman untuk produksi.
    // UNTUK PRODUKSI, Anda perlu set sertifikat CA (Certificate Authority) Root.
    client.setInsecure(); // HANYA UNTUK PENGEMBANGAN!
    // Contoh untuk produksi: client.setCACert(ISRG_ROOT_X1_CA_CERT); (ISRG_ROOT_X1_CA_CERT adalah string sertifikat)

    if (client.connect(mqtt_client_id, mqtt_user, mqtt_password)) {
      Serial.println("MQTT Connected!");
      // Subscribe ke topik kontrol setelah berhasil terhubung
      client.subscribe(mqtt_topic_subscribe_control);
      Serial.print("Subscribed to MQTT topic: ");
      Serial.println(mqtt_topic_subscribe_control);
    } else {
      Serial.print("MQTT connection failed, rc=");
      Serial.print(client.state());
      Serial.println(". Retrying in 5 seconds...");
      delay(5000); // Tunggu 5 detik sebelum mencoba lagi
    }
  }
}

// --- SETUP UTAMA (Jalankan sekali saat ESP32 pertama kali menyala) ---
void setup() {
  Serial.begin(115200); // Inisialisasi Serial Monitor
  pinMode(LED_PIN, OUTPUT); // Inisialisasi pin untuk LED (simulasi lampu)

  // 1. Setup WiFi (untuk koneksi ke internet / HiveMQ Cloud)
  setup_wifi();

  // 2. Setup MQTT Client
  client.setServer(mqtt_broker, mqtt_port);
  client.setCallback(mqttCallback); // Set fungsi callback untuk pesan MQTT masuk dari Cloud

  // 3. Setup painlessMesh
  // mesh.setDebugMsgLevel( (MeshDebug)LOG_ERROR ); // Hanya tampilkan error untuk debugging Mesh
  mesh.init( MESH_PREFIX, MESH_PASSWORD, MESH_PORT );
  mesh.onReceive(&receivedCallback);          // Callback saat pesan diterima dari Mesh
  mesh.onNewConnection(&newConnectionCallback); // Callback saat ada node baru terhubung ke Mesh
  mesh.onChangedConnections(&changedConnectionsCallback); // Callback saat koneksi Mesh berubah
  mesh.onNodeTimeAdjusted(&nodeTimeAdjustedCallback); // Callback saat waktu node disesuaikan di Mesh

  // Menentukan Gateway adalah node yang terhubung ke WiFi (Internet).
  // Ini penting agar painlessMesh tahu siapa yang bertanggung jawab untuk koneksi luar.
  mesh.setContainsRoot(true);
}

// --- LOOP UTAMA (Jalankan terus menerus setelah setup) ---
void loop() {
  // Penting: Panggil mesh.update() di awal loop untuk menjaga jaringan Mesh
  mesh.update();

  // Pastikan koneksi MQTT ke Cloud tetap aktif
  if (!client.connected()) {
    reconnect_mqtt(); // Jika tidak terhubung, coba hubungkan kembali
  }
  client.loop(); // Memproses pesan masuk MQTT dan menjaga koneksi

  // --- Bagian ini opsional jika Gateway hanya meneruskan data dari Mesh ---
  // Jika Gateway ini juga memiliki sensor sendiri dan perlu mempublikasikan data secara berkala,
  // atau hanya untuk mengirim pesan keep-alive ke Cloud secara berkala.
  // unsigned long currentMillis = millis();
  // if (currentMillis - lastPublishMillis > publishInterval) {
  //   lastPublishMillis = currentMillis;
  //
  //   // Contoh publikasi data dari Gateway itu sendiri (jika ada sensor di Gateway)
  //   // StaticJsonDocument<200> doc;
  //   // doc["gateway_temp"] = 28.5; // Contoh data
  //   // doc["gateway_humidity"] = 70.0;
  //   // char jsonBuffer[200];
  //   // serializeJson(doc, jsonBuffer);
  //   //
  //   // Serial.print("Publishing Gateway data to: ");
  //   // Serial.println(mqtt_topic_publish_sensor);
  //   // client.publish(mqtt_topic_publish_sensor, jsonBuffer);
  // }
}