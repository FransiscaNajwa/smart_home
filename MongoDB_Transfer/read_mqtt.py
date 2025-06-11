import json
from pymongo import MongoClient
import paho.mqtt.client as mqtt

# Konfigurasi MongoDB
uri = "mongodb+srv://alfarrelmahardika:<password>@cluster0.lnbl9.mongodb.net/"
client = MongoClient(uri)
db = client["managemen_listrik"]
collection = db["kipas"]

# Fungsi callback saat berhasil connect ke MQTT Broker
def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe("jarkom/monitoring/managemendaya")

# Fungsi callback saat pesan diterima dari MQTT
def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        print("Received MQTT data:", data)

        # Simpan ke MongoDB
        result = collection.insert_one(data)
        print("Inserted document ID:", result.inserted_id)

    except Exception as e:
        print("Error processing message:", e)

# Konfigurasi MQTT
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set("hivemq.webclient.1749548766220", "1uBpWUE9<:jAq5>6d#bY")
mqtt_client.tls_set()  # TLS karena broker pakai port 8883
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.connect("8bda2df24fea4d2c9aadeb89eedd2738.s1.eu.hivemq.cloud", 8883)

# Jalankan loop
mqtt_client.loop_forever()
