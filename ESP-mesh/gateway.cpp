#include "painlessMesh.h"
#include <ESP8266WiFi.h>
#include <PubSubClient.h>

#define MESH_PREFIX "myMesh"
#define MESH_PASSWORD "meshPassword"
#define MESH_PORT 5555

#define WIFI_SSID "Yoru no Hajimarisa"
#define WIFI_PASSWORD "bunnygirl"
#define MQTT_SERVER "d2ef03a20bbd46239e855ff4422e7a78.s1.eu.hivemq.cloud"
#define MQTT_PORT 8883
#define MQTT_TOPIC "jarkom/mesh/data"
#define MQTT_USERNAME "hivemq.webclient.1748944809100"
#define MQTT_PASSWORD "6:%0JBFfG1dg.3$liSbA"

Scheduler userScheduler;
painlessMesh mesh;
WiFiClient espClient;
PubSubClient client(espClient);

void receivedCallback(uint32_t from, String &msg) {
  Serial.printf("Received from %u: %s\n", from, msg.c_str());
  if (client.connected()) {
    client.publish(MQTT_TOPIC, msg.c_str());
    Serial.println("Published to MQTT");
  } else {
    Serial.println("MQTT not connected, cannot publish");
  }
}

void connectToMQTT() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!client.connected()) {
      Serial.println("Attempting MQTT connection...");
      if (client.connect("ESP8266Gateway", MQTT_USERNAME, MQTT_PASSWORD)) {
        Serial.println("Connected to MQTT");
      } else {
        Serial.print("Failed to connect to MQTT, state: ");
        Serial.println(client.state());
      }
    }
  } else {
    Serial.println("Wi-Fi not connected");
  }
}

Task taskConnectMQTT(TASK_SECOND * 5, TASK_FOREVER, &connectToMQTT);

void setup() {
  Serial.begin(115200);
  mesh.setDebugMsgTypes(ERROR | STARTUP);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  mesh.stationManual(WIFI_SSID, WIFI_PASSWORD);
  client.setServer(MQTT_SERVER, MQTT_PORT);
  mesh.onReceive(&receivedCallback);
  userScheduler.addTask(taskConnectMQTT);
  taskConnectMQTT.enable();
}

void loop() {
  mesh.update();
  client.loop();
}