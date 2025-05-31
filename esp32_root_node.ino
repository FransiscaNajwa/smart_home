#include <WiFi.h>
#include <PubSubClient.h>   // Library untuk MQTT
#include <ArduinoJson.h>    // Library untuk JSON
#include <painlessMesh.h>   // Library untuk Mesh Networking
#include <Wire.h>           // Untuk sensor BH1750
#include <BH1750.h>         // Untuk sensor cahaya
#include <DHT.h>            // Untuk sensor suhu/kelembaban

// --- KONFIGURASI ROLE PERANGKAT ---
// Uncomment baris berikut untuk mengatur perangkat sebagai Gateway saat mengunggah kode
//#define GATEWAY

// --- KONFIGURASI WIFI (Untuk Gateway terhubung ke Router) ---
#ifdef GATEWAY
const char* ssid = "RESTU";
const char* password = "restu547";
#endif

// --- KONFIGURASI MQTT (Untuk Gateway terhubung ke HiveMQ Cloud) ---
#ifdef GATEWAY
const char* mqtt_broker = "90c69dacebc2450495a401b6550d787b.s1.eu.hivemq.cloud"; // GANTI DENGAN HOSTNAME ASLI ANDA!
const int mqtt_port = 8883; // Port SSL/TLS
const char* mqtt_user = "smarthome_iot_devices";         // GANTI DENGAN USERNAME ASLI ANDA!
const char* mqtt_password = "Smarthome99";              // GANTI DENGAN PASSWORD ASLI ANDA!
const char* mqtt_client_id = "ESP32_Gateway_001";       // ID klien unik untuk Gateway
#endif

// --- KONFIGURASI TOPIK MQTT ---
#ifdef GATEWAY
const char* mqtt_topic_publish_sensor = "starswechase/sungai/mesh_sensor_data";
const char* mqtt_topic_subscribe_control = "starswechase/sungai/control/#"; // Menggunakan '#' untuk semua sub-topik
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
const long publishInterval = 30000; // 30 detik untuk Gateway (opsional)
Task allSensorDataTask(5000, TASK_FOREVER, &sendAllSensorData); // 5 detik untuk Node

// --- MESH CALLBACKS ---
void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Received from Mesh node %u: %s\n", from, msg.c_str());

  #ifdef GATEWAY
    // Gateway meneruskan pesan ke HiveMQ Cloud
    Serial.print("Publishing Mesh data to MQTT Cloud on topic: ");
    Serial.println(mqtt_topic_publish_sensor);
    client.publish(mqtt_topic_publish_sensor, msg.c_str());
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
      if (state == "ON") {
        digitalWrite(LED_PIN, HIGH);
        Serial.println("LAMPU DINYALAKAN");
      } else if (state == "OFF") {
        digitalWrite(LED_PIN, LOW);
        Serial.println("LAMPU DIMATIKAN");
      }
    } else if (device == "kipas") {
      if (state == "ON") {
        digitalWrite(MOTOR_PIN, HIGH);
        Serial.println("KIPAS DINYALAKAN");
      } else if (state == "OFF") {
        digitalWrite(MOTOR_PIN, LOW);
        Serial.println("KIPAS DIMATIKAN");
      }
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
  Serial.print("Message arrived from Cloud on topic: ");
  Serial.println(topic);
  String messageTemp;
  for (int i = 0; i < length; i++) {
    messageTemp += (char)payload[i];
  }
  Serial.print("Payload: ");
  Serial.println(messageTemp);

  if (String(topic) == "starswechase/sungai/control/lampu") {
    if (messageTemp == "ON") {
      mesh.sendBroadcast("{\"device\":\"lampu\",\"state\":\"ON\"}");
      Serial.println("LED ON command broadcasted");
    } else if (messageTemp == "OFF") {
      mesh.sendBroadcast("{\"device\":\"lampu\",\"state\":\"OFF\"}");
      Serial.println("LED OFF command broadcasted");
    }
  } else if (String(topic) == "starswechase/sungai/control/kipas") {
    if (messageTemp == "ON") {
      mesh.sendBroadcast("{\"device\":\"kipas\",\"state\":\"ON\"}");
      Serial.println("FAN ON command broadcasted");
    } else if (messageTemp == "OFF") {
      mesh.sendBroadcast("{\"device\":\"kipas\",\"state\":\"OFF\"}");
      Serial.println("FAN OFF command broadcasted");
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

  if (isnan(h) || isnan(t)) {
    Serial.println("Gagal membaca dari sensor DHT");
    h = -1.0;
    t = -1.0;
  }
  if (lux < 0) {
    Serial.println("Gagal membaca dari sensor BH1750");
    lux = -1.0;
  }

  String msg = "{";
  msg += "\"node\":\"sensor_control_node\",";
  msg += "\"lux\":" + String(lux, 2) + ",";
  msg += "\"temperature\":" + String(t, 1) + ",";
  msg += "\"humidity\":" + String(h, 1);
  msg += "}";

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
    client.setInsecure(); // HANYA UNTUK PENGEMBANGAN, GANTI DENGAN SERTIFIKAT CA UNTUK PRODUKSI
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

    // Opsional: Publikasi data Gateway (jika ada sensor di Gateway)
    unsigned long currentMillis = millis();
    if (currentMillis - lastPublishMillis > publishInterval) {
      lastPublishMillis = currentMillis;
      // Tambahkan logika publikasi data Gateway jika ada sensor
    }
  #endif
}