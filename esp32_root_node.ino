#include <WiFi.h>
#include <PubSubClient.h>
#include <painlessMesh.h>
#include <ArduinoJson.h>
#include <NTPClient.h>
#include <WiFiUdp.h>

const char* ssid = "";
const char* password = "";

// MQTT Configuration for HiveMQ Cloud
const char* mqtt_broker = "68c1b8e40d134f6c898d4d31b1d85940.s1.eu.hivemq.cloud";
const int mqtt_port = 8883;
const char* mqtt_user = "hivemq.webclient.1748947445091"; // Kredensial baru dari HiveMQ
const char* mqtt_password = ".4@57oHKlAn:,BcV3pMd"; // Ganti dengan password dari HiveMQ
const char* mqtt_client_id = "ESP32_Gateway_001";

const char* mqtt_topic_publish_sensor = "smart_home/data";
const char* mqtt_topic_subscribe_control = "smart_home/control/#";

#define MESH_PREFIX "SmartHomeMesh"
#define MESH_PASSWORD "mesh_jarkom_123"
#define MESH_PORT 5555

painlessMesh mesh;
WiFiClient espClient;
PubSubClient client(espClient);
Scheduler userScheduler;
unsigned long lastPublishMillis = 0;
const long publishInterval = 30000;

#define LED_PIN 5       // I/O5 untuk kontrol lampu
#define ACS712_PIN 34   // ADC pin untuk sensor arus
Task sensorDataTask(10000, TASK_FOREVER, &sendSensorData);

// NTP Configuration
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", 25200, 60000); // WIB = UTC+7

// Fungsi untuk membaca arus dari ACS712 dengan filter
float readCurrent() {
  const int samples = 10;
  float total = 0;
  for (int i = 0; i < samples; i++) {
    int rawValue = analogRead(ACS712_PIN);
    if (rawValue < 0 || rawValue > 4095) return -1; // Error detection
    float voltage = (rawValue / 4095.0) * 5.0;
    float current = (voltage - 2.5) / 0.066;
    total += current > 0 ? current : 0;
    delay(10);
  }
  float avgCurrent = total / samples;
  return avgCurrent > 0.01 ? avgCurrent : 0; // Minimum threshold 0.01A
}

// Fungsi untuk mengirim data sensor lampu
void sendSensorData() {
  float current = readCurrent();
  if (current < 0) {
    Serial.println("Error reading ACS712");
    return;
  }
  float watt = 5.0 * current;
  timeClient.update();
  String timestamp = timeClient.getFormattedTime();
  DynamicJsonDocument doc(128);
  doc["device"] = "lampu";
  doc["status"] = digitalRead(LED_PIN) == LOW ? "ON" : "OFF";
  doc["current"] = current;
  doc["watt"] = watt;
  doc["timestamp"] = timestamp;

  String msg;
  serializeJson(doc, msg);
  mesh.sendBroadcast(msg);
  Serial.println("Terkirim via Mesh: " + msg);
  if (client.connected()) {
    if (!client.publish(mqtt_topic_publish_sensor, msg.c_str())) {
      Serial.println("Failed to publish to HiveMQ");
    } else {
      Serial.println("Published to HiveMQ: " + msg);
    }
  }
}

// Callback untuk menerima pesan dari mesh atau MQTT
void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Received from Mesh node %u: %s\n", from, msg.c_str());
  DynamicJsonDocument doc(256);
  DeserializationError error = deserializeJson(doc, msg);
  if (error) {
    Serial.println("deserializeJson() failed");
    return;
  }
  String device = doc["device"];
  String state = doc["state"];
  if (device == "lampu") {
    digitalWrite(LED_PIN, state == "ON" ? LOW : HIGH);
    Serial.println(state == "ON" ? "LAMPU DINYALAKAN" : "LAMPU DIMATIKAN");
  }
  if (client.connected()) {
    if (!client.publish(mqtt_topic_publish_sensor, msg.c_str())) {
      Serial.println("Failed to publish to HiveMQ");
    } else {
      Serial.println("Published to HiveMQ: " + msg);
    }
  }
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

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String topicStr = topic;
  String messageTemp;
  for (int i = 0; i < length; i++) {
    messageTemp += (char)payload[i];
  }
  Serial.print("Message arrived on topic: ");
  Serial.println(topicStr);
  if (topicStr.startsWith("smart_home/control/")) {
    String device = topicStr.substring(13);
    if (device == "lampu" || device == "kipas") {
      String state = messageTemp;
      mesh.sendBroadcast("{\"device\":\"" + device + "\",\"state\":\"" + state + "\"}");
    }
  }
}

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
    if (retries > 20) ESP.restart();
  }
  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println(WiFi.localIP());
}

void reconnect_mqtt() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection to HiveMQ...");
    client.setBufferSize(1024);
    if (client.connect(mqtt_client_id, mqtt_user, mqtt_password)) {
      Serial.println("MQTT Connected to HiveMQ!");
      client.subscribe(mqtt_topic_subscribe_control);
    } else {
      Serial.print("MQTT connection failed, rc=");
      Serial.print(client.state());
      Serial.println(". Retrying in 5 seconds...");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH); // Matikan awalnya
  setup_wifi();
  client.setServer(mqtt_broker, mqtt_port);
  client.setCallback(mqttCallback);
  client.setSocketTimeout(10);
  client.setKeepAlive(60);
  client.tls_set();
  timeClient.begin();
  mesh.setDebugMsgTypes(ERROR | STARTUP | CONNECTION);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  mesh.onReceive(&receivedCallback);
  mesh.onNewConnection(&newConnectionCallback);
  mesh.onChangedConnections(&changedConnectionsCallback);
  mesh.onNodeTimeAdjusted(&nodeTimeAdjustedCallback);
  mesh.setContainsRoot(true);
  userScheduler.addTask(sensorDataTask);
  sensorDataTask.enable();
  sendSensorData();
}

void loop() {
  mesh.update();
  if (!client.connected()) reconnect_mqtt();
  client.loop();
  unsigned long currentMillis = millis();
  if (currentMillis - lastPublishMillis > publishInterval) {
    lastPublishMillis = currentMillis;
    client.publish(mqtt_topic_publish_sensor, "{\"status\":\"keep-alive\"}");
  }
}