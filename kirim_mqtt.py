import paho.mqtt.client as mqtt
import time
import ssl

# MQTT Broker configuration
broker = "8bda2df24fea4d2c9aadeb89eedd2738.s1.eu.hivemq.cloud"
port = 8883
username = "hivemq.webclient.1749548766220"
password = "1uBpWUE9<:jAq5>6d#bY"
topic = "iot/perintah/relay_on_off"

# Callback when the client connects to the broker
def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("Connected to MQTT Broker!")
    else:
        print(f"Failed to connect, return code {reason_code}")

# Create MQTT client
client = mqtt.Client(client_id="", protocol=mqtt.MQTTv5)
client.username_pw_set(username, password)
client.tls_set(tls_version=ssl.PROTOCOL_TLS)
client.on_connect = on_connect

# Connect to the broker
client.connect(broker, port)

# Start the loop to process network events
client.loop_start()

try:
    while True:
        # Publish message "1" to the topic
        client.publish(topic, "0", qos=1)
        print(f"Published '0' to topic {topic}")
        time.sleep(10)  # Wait for 10 seconds
except KeyboardInterrupt:
    print("Stopped by user")
finally:
    client.loop_stop()
    client.disconnect()
    print("Disconnected from MQTT Broker")