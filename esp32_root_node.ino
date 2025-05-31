#include <WiFi.h>
#include <PubSubClient.h>   // Library untuk MQTT
#include <ArduinoJson.h>    // Library untuk JSON
#include <painlessMesh.h>   // Library untuk Mesh Networking
#include <Wire.h>           // Untuk sensor BH1750
#include <BH1750.h>         // Untuk sensor cahaya
#include <DHT.h>            // Untuk sensor suhu/kelembaban

// --- KONFIGURASI ROLE PERANGKAT ---
// Uncomment baris berikut untuk mengatur perangkat sebagai Gateway saat mengunggah kode
#define GATEWAY

// --- KONFIGURASI WIFI (Untuk Gateway terhubung ke Router) ---
#ifdef GATEWAY
const char* ssid = "RESTU";
const char* password = "restu547";
#endif

// --- KONFIGURASI MQTT (Untuk Gateway terhubung ke HiveMQ Cloud) ---
#ifdef GATEWAY
const char* mqtt_broker = "6f820295b0364ee293a9a96c1f2457a6.s1.eu.hivemq.cloud"; // Hostname HiveMQ Cloud
const int mqtt_port = 8883; // Port SSL/TLS
const char* mqtt_user = "hivemq.webclient.1748687406394";         // Username
const char* mqtt_password = "K0p.D,9ErwiU!W51kS&n";              // Password
const char* mqtt_client_id = "ESP32_Gateway_001";       // ID klien unik
#endif

// --- KONFIGURASI TOPIK MQTT ---
#ifdef GATEWAY
const char* mqtt_topic_publish_sensor = "starswechase/sungai/data";
const char* mqtt_topic_subscribe_control = "starswechase/sungai/control/#"; // Wildcard untuk semua sub-topik
#endif

// --- KONFIGURASI MESH (painlessMesh) ---
#define MESH_PREFIX "SmartHomeMesh"
#define MESH_PASSWORD "mesh_jarkom_123"
#define MESH_PORT 5555

painlessMesh mesh;

// --- DEFINISI PIN UNTUK NODE ---
#ifndef GATEWAY
#define LED_PIN 2       // Pin untuk LED (lampu)
#define DHTPIN 4        // Pin untuk DHT11
#define DHTTYPE DHT11
#define MOTOR_PIN 15    // Pin untuk motor (kipas)
#endif

// Objek sensor (hanya untuk Node)
#ifndef GATEWAY
BH1750 lightMeter;
DHT dht(DHTPIN, DHTTYPE);
#endif

// Inisialisasi klien WiFi dan MQTT (hanya untuk Gateway)
#ifdef GATEWAY
WiFiClient espClient;
PubSubClient client(espClient);
#endif

// Variabel untuk Task dan interval
Scheduler userScheduler;
unsigned long lastPublishMillis = 0;
const long publishInterval = 30000; // 30 detik untuk Gateway
Task allSensorDataTask(10000, TASK_FOREVER, &sendAllSensorData); // 10 detik untuk Node

// --- MESH CALLBACKS ---
void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Received from Mesh node %u: %s\n", from, msg.c_str());

  #ifdef GATEWAY
    // Gateway meneruskan pesan ke HiveMQ Cloud
    if (client.connected()) {
      Serial.print("Publishing Mesh data to MQTT Cloud on topic: ");
      Serial.println(mqtt_topic_publish_sensor);
      client.publish(mqtt_topic_publish_sensor, msg.c_str());
    } else {
      Serial.println("MQTT not connected, data not published.");
    }
  #else
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
    } else if (device == "kipas") {
      digitalWrite(MOTOR_PIN, state == "ON" ? HIGH : LOW);
      Serial.println(state == "ON" ? "KIPAS DINYALAKAN" : "KIPAS DIMATIKAN");
    }
  #endif
}

void newConnectionCallback(uint32_t nodeId) {
  Serial.printf("New connection from Mesh node %u\n", nodeId);
}

void changedConnectionsCallback() {
  Serial.printf("Changed connections. Total nodes: %d\n", mesh.getNodeList().size());
}

void nodeTimeAdjustedCallback(int32_t offset) {
  Serial.printf("Adjusted time %u. Offset = %d\n", mesh.getNodeTime(), offset);
}

// --- MQTT CALLBACK (Hanya untuk Gateway) ---
#ifdef GATEWAY
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String topicStr = topic;
  String messageTemp;
  for (int i = 0; i < length; i++) {
    messageTemp += (char)payload[i];
  }
  Serial.print("Message arrived on topic: ");
  Serial.println(topicStr);
  Serial.print("Payload: ");
  Serial.println(messageTemp);

  if (topicStr.startsWith("starswechase/sungai/control/")) {
    String device = topicStr.substring(23); // Ambil bagian setelah "control/"
    if (device == "lampu" || device == "kipas") {
      String state = messageTemp;
      mesh.sendBroadcast("{\"device\":\"" + device + "\",\"state\":\"" + state + "\"}");
      Serial.println(device + " " + state + " command broadcasted");
    }
  }
}
#endif

// --- FUNGSI NODE (Mengirim Data Sensor) ---
#ifndef GATEWAY
void sendAllSensorData() {
  float lux = lightMeter.readLightLevel();
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t) || lux < 0) {
    Serial.println("Gagal membaca dari salah satu sensor, melewatkan pengiriman.");
    return; // Melewatkan pengiriman jika ada data tidak valid
  }

  DynamicJsonDocument doc(128);
  doc["node"] = "sensor_control_node";
  doc["lux"] = lux;
  doc["temperature"] = t;
  doc["humidity"] = h;

  String msg;
  serializeJson(doc, msg);
  mesh.sendBroadcast(msg);
  Serial.println("Terkirim: " + msg);
}
#endif

// --- FUNGSI KONEKSI WIFI (Hanya untuk Gateway) ---
#ifdef GATEWAY
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
    if (retries > 20) {
      Serial.println("\nFailed to connect to WiFi. Restarting...");
      ESP.restart();
    }
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}
#endif

// --- FUNGSI REKONEKSI MQTT (Hanya untuk Gateway) ---
#ifdef GATEWAY
void reconnect_mqtt() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Tambahkan sertifikat CA untuk koneksi aman (ganti dengan file CA HiveMQ)
    client.setBufferSize(1024); // Tingkatkan buffer untuk pesan besar
    if (client.connect(mqtt_client_id, mqtt_user, mqtt_password)) {
      Serial.println("MQTT Connected!");
      client.subscribe(mqtt_topic_subscribe_control);
      Serial.print("Subscribed to MQTT topic: ");
      Serial.println(mqtt_topic_subscribe_control);
    } else {
      Serial.print("MQTT connection failed, rc=");
      Serial.print(client.state());
      Serial.println(". Retrying in 5 seconds...");
      delay(5000);
    }
  }
}
#endif

// --- SETUP UTAMA ---
void setup() {
  Serial.begin(115200);

  #ifndef GATEWAY
    // Inisialisasi sensor untuk Node
    Wire.begin(21, 22); // SDA, SCL untuk ESP32 (sesuaikan jika berbeda)
    if (!lightMeter.begin()) {
      Serial.println("Error initializing BH1750!");
      while (1);
    }
    dht.begin();
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);
    pinMode(MOTOR_PIN, OUTPUT);
    digitalWrite(MOTOR_PIN, LOW);

    // Inisialisasi Mesh untuk Node
    mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
    mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
    mesh.onReceive(&receivedCallback);
    userScheduler.addTask(allSensorDataTask);
    allSensorDataTask.enable();
    sendAllSensorData(); // Kirim data pertama kali
  #else
    // Inisialisasi untuk Gateway
    setup_wifi();
    client.setServer(mqtt_broker, mqtt_port);
    client.setCallback(mqttCallback);
    pinMode(LED_PIN, OUTPUT); // Opsional, untuk simulasi kontrol lokal
    digitalWrite(LED_PIN, LOW);

    // Inisialisasi Mesh untuk Gateway
    mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
    mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
    mesh.onReceive(&receivedCallback);
    mesh.onNewConnection(&newConnectionCallback);
    mesh.onChangedConnections(&changedConnectionsCallback);
    mesh.onNodeTimeAdjusted(&nodeTimeAdjustedCallback);
    mesh.setContainsRoot(true); // Tetapkan sebagai root node
  #endif
}

// --- LOOP UTAMA ---
void loop() {
  mesh.update();

  #ifdef GATEWAY
    if (!client.connected()) {
      reconnect_mqtt();
    }
    client.loop();

    // Publikasi data dummy untuk menjaga koneksi MQTT aktif
    unsigned long currentMillis = millis();
    if (currentMillis - lastPublishMillis > publishInterval) {
      lastPublishMillis = currentMillis;
      client.publish(mqtt_topic_publish_sensor, "{\"status\":\"keep-alive\"}");
      Serial.println("Published keep-alive message to MQTT");
    }
  #endif
}