#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#define ACS_712        A0 // GPIO34 (ADC1_CHANNEL_6)
#define ON_OFF_RELAY   D6
#define ALL_TIME_HIGH  D7

const char* ssid = "Galaxy";
const char* password = "Alfarrel";
const char* mqtt_broker = "8bda2df24fea4d2c9aadeb89eedd2738.s1.eu.hivemq.cloud";
const int mqtt_port = 8883;
const char* mqtt_username = "hivemq.webclient.1749548766220";
const char* mqtt_password = "1uBpWUE9<:jAq5>6d#bY";

#define ACS712_SENSITIVITY 0.100 // For ACS712-20A (adjust if using 5A: 0.185, or 30A: 0.066)
#define MAX_SAMPLES 120 // 60 seconds / 0.5 seconds per sample = 120 samples

float offset = 0;
int adc = 0;
float voltage = 0.0;
float current = 0.0;
bool relayState = false;

WiFiClientSecure espClient;
PubSubClient client(espClient);

const unsigned long publishInterval = 60000; // 60 seconds in milliseconds
unsigned long lastPublishTime = 0;

// Arrays to store samples
struct Sample {
  unsigned long timestamp;
  float voltage;
  float current;
  int relay;
};
Sample samples[MAX_SAMPLES];
int sampleCount = 0;

int readAverageADC(int pin, int samples = 20) {
  long total = 0;
  int validReadings = 0;
  for (int i = 0; i < samples; i++) {
    int value = analogRead(pin);
    if (value > 0) { // Ignore invalid readings
      total += value;
      validReadings++;
    }
    delay(2);
  }
  if (validReadings == 0) {
    Serial.println("No valid ADC readings!");
    return 0;
  }
  return total / validReadings;
}

void onofflamp(bool state) {
  relayState = state;
  digitalWrite(ON_OFF_RELAY, state ? HIGH : LOW);
  Serial.println(state ? "Relay ON (ACS mati)" : "Relay OFF (ACS aktif)");
}

void callback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  if (String(topic) == "iot/perintah/relay_lampu") {
    if (message == "1") {
      onofflamp(true);
    } else if (message == "0") {
      onofflamp(false);
    }
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("", mqtt_username, mqtt_password)) {
      Serial.println("connected");
      client.subscribe("iot/perintah/relay_lampu");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(ON_OFF_RELAY, OUTPUT);
  pinMode(ALL_TIME_HIGH, OUTPUT);
  digitalWrite(ALL_TIME_HIGH, HIGH);

  // WiFi setup
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");

  // Configure WiFiClientSecure
  espClient.setInsecure(); // Skip certificate verification (use with caution)

  // MQTT setup
  client.setServer(mqtt_broker, mqtt_port);
  client.setCallback(callback);

  // Calibrate offset
  long total = 0;
  int validReadings = 0;
  for (int i = 0; i < 100; i++) {
    int value = analogRead(ACS_712);
    if (value > 0) {
      Serial.print("Calibration ADC: "); Serial.println(value);
      total += value;
      validReadings++;
    }
    delay(5);
  }
  if (validReadings == 0) {
    Serial.println("Calibration failed: No valid ADC readings!");
    offset = 2.224; // Fallback to expected offset
  } else {
    offset = total / (float)validReadings; 
  }
  Serial.print("Offset voltage (no current): ");
  Serial.println(offset, 3);

  configTime(25200, 0, "pool.ntp.org", "time.nist.gov");
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Read and store sample
  if (!relayState) {
    Serial.println("Reading ACS712...");
    adc = readAverageADC(ACS_712);
    if (adc == 0) {
      voltage = 0.0;
      current = 0.0;
    } else {
      voltage = adc * 3.3 / 1023.0;
      current = ((float)adc - offset) * (3.3 / 1023.0) / ACS712_SENSITIVITY;
      if (current < 0) current = 0.0; // Clamp negative current
    }
    Serial.print("Calculated voltage: "); Serial.println(voltage, 3);
    Serial.print("Calculated current: "); Serial.println(current, 3);
  } else {
    voltage = 0.0;
    current = 0.0;
  }

  // Store sample
  if (sampleCount < MAX_SAMPLES) {
    samples[sampleCount].timestamp = millis();
    samples[sampleCount].voltage = voltage;
    samples[sampleCount].current = current;
    samples[sampleCount].relay = relayState ? 1 : 0;
    sampleCount++;
  }

  // Serial output
  Serial.print("ADC: ");
  Serial.print(adc);
  Serial.print(" | Voltage: ");
  Serial.print(voltage, 3);
  Serial.print(" V | Current: ");
  Serial.print(current, 2);
  Serial.print(" A | Relay: ");
  Serial.println(relayState ? "ON" : "OFF");

  // Publish to MQTT every 60 seconds
  unsigned long currentTime = millis();
   if (currentTime - lastPublishTime >= publishInterval) {
    // Hitung rata-rata daya (Watt) per menit
    float totalWatt = 0.0;
    for (int i = 0; i < sampleCount; i++) {
      float watt = samples[i].voltage * samples[i].current;
      totalWatt += watt;
    }
    float averageWatt = sampleCount > 0 ? totalWatt / sampleCount : 0.0;

    // Ambil waktu sekarang (dalam WIB)
    time_t now;
    struct tm timeinfo;
    if (!getLocalTime(&timeinfo)) {
      Serial.println("Gagal mendapatkan waktu lokal");
      return;
    }
    char timestamp[25];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", &timeinfo);

    // Buat JSON payload
    StaticJsonDocument<1024> doc;
    doc["device_id"]= 1;
    doc["relay"] = relayState ? 1 : 0;
    doc["watt"] = averageWatt;
    doc["timestamp"] = timestamp;

    char buffer[512];
    serializeJson(doc, buffer);

    // Publish ke MQTT
    if (client.publish("jarkom/monitoring/managemendaya", buffer)) {
      Serial.println("MQTT watt data published");
    } else {
      Serial.println("MQTT publish failed");
    }

    // Reset sample
    sampleCount = 0;
    lastPublishTime = currentTime;
  }


  delay(500);
}