import paho.mqtt.client as mqtt
import ssl
import json
import time
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# MongoDB connection details
uri = "mongodb+srv://alfarrelmahardika:Z.iLkvVg7Ep6!uP@cluster0.lnbl9.mongodb.net/"
db_name = "manajemen_listrik"
collection_name = "kipas_dan_lampu"

# MQTT broker details
broker = "8bda2df24fea4d2c9aadeb89eedd2738.s1.eu.hivemq.cloud"
port = 8883
username = "hivemq.webclient.1749548766220"
password = "1uBpWUE9<:jAq5>6d#bY"
topic = "jarkom/monitoring/managemendaya"

# Initialize MongoDB client
try:
    mongo_client = MongoClient(uri)
    db = mongo_client[db_name]
    collection = db[collection_name]
    # Test the connection
    mongo_client.admin.command('ping')
    print("✅ Successfully connected to MongoDB")
except ConnectionFailure as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    exit(1)

# Callback when connecting to the MQTT broker
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("✅ Connected to MQTT broker")
        client.subscribe(topic, qos=1)
        print(f"📡 Subscribed to topic: {topic}")
    else:
        print(f"❌ Connection failed with code {rc}")

# Callback when a message is received
def on_message(client, userdata, msg):
    print(f"\n📩 Message received on topic: {msg.topic}")
    try:
        data = json.loads(msg.payload.decode('utf-8'))
        print("📄 Parsed JSON data:")

        # Ambil data sesuai format JSON flat (tanpa array 'data')
        device_id = data.get('device_id', 'N/A')
        relay = data.get('relay', 'N/A')
        watt = data.get('watt', 'N/A')
        timestamp = data.get('timestamp', 'N/A')

        # Tampilkan ke terminal
        print(f"  Timestamp: {timestamp}, Watt: {watt} W, Relay: {relay}, Device ID: {device_id}")

        # Buat dokumen untuk MongoDB
        document = {
            "device_id": device_id,
            "timestamp": timestamp,
            "watt": float(watt) if watt != 'N/A' else None,
            "relay": relay,
            "topic": msg.topic,
        }

        # Insert ke MongoDB
        try:
            collection.insert_one(document)
            print("✅ Data inserted into MongoDB")
        except Exception as e:
            print(f"❌ Error inserting into MongoDB: {e}")
    
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"Raw payload: {msg.payload.decode('utf-8')}")
    except Exception as e:
        print(f"❌ Error processing message: {e}")

# Callback ketika berhasil subscribe
def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    print(f"📥 Subscription confirmed: mid={mid}, QoS={granted_qos}")

# Buat MQTT client
client = mqtt.Client(client_id="", protocol=mqtt.MQTTv5)

# Set kredensial MQTT
client.username_pw_set(username, password)

# Atur TLS (gunakan dengan hati-hati, ini melewati verifikasi sertifikat)
client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2, cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)

# Set callback
client.on_connect = on_connect
client.on_message = on_message
client.on_subscribe = on_subscribe

# Hubungkan ke broker
try:
    client.connect(broker, port, keepalive=60)
except Exception as e:
    print(f"❌ Failed to connect to broker: {e}")
    exit(1)

# Mulai loop untuk proses MQTT
client.loop_start()

# Biarkan program berjalan terus
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n⏹️ Disconnecting from broker and MongoDB")
    client.loop_stop()
    client.disconnect()
    mongo_client.close()
