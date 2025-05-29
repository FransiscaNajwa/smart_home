from flask import Flask, jsonify
import paho.mqtt.client as mqtt
from pymongo import MongoClient
from datetime import datetime, timedelta
import json, random, threading
import os 

# === Konfigurasi MongoDB ===
mongo_uri = os.environ.get("MONGO_URI", "mongodb+srv://smarthome:smarthome99@cluster0.kaomhbl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
MONGO_DB_NAME = "smart_home"
SENSOR_COLLECTION_NAME = "mesh_sensor_data" # Ganti nama koleksi untuk data mesh
DEVICE_STATUS_COLLECTION_NAME = "device_status" 

mongo_client = None
db = None
sensor_collection = None
device_status_collection = None
db_connected = False

def connect_to_mongodb():
    global mongo_client, db, sensor_collection, device_status_collection, db_connected
    try:
        mongo_client = MongoClient(mongo_uri)
        mongo_client.admin.command("ping")
        db = mongo_client[MONGO_DB_NAME]
        sensor_collection = db[SENSOR_COLLECTION_NAME]
        device_status_collection = db[DEVICE_COLLECTION_NAME] # Tetap gunakan koleksi ini untuk status perangkat
        db_connected = True
        print("[MongoDB] Connected successfully.")
        
        # Anda mungkin ingin menambahkan logika untuk inisialisasi status lampu/kipas per device_id dari ESP-NOW
        # Daripada hanya 'lampu' dan 'kipas', mungkin 'Node1_lampu', 'Node1_kipas', dll.
        # Atau biarkan status "OFF" global yang diupdate saat ada data sensor
        
        # Contoh inisialisasi untuk Node1
        if device_status_collection.find_one({"device": "Node1_lampu"}) is None:
            device_status_collection.insert_one({"device": "Node1_lampu", "state": "OFF", "last_updated": datetime.now()})
            print("[MongoDB] Initial status for 'Node1_lampu' added.")
        if device_status_collection.find_one({"device": "Node1_kipas"}) is None:
            device_status_collection.insert_one({"device": "Node1_kipas", "state": "OFF", "last_updated": datetime.now()})
            print("[MongoDB] Initial status for 'Node1_kipas' added.")


    except Exception as e:
        print(f"[MongoDB] Connection failed: {e}")
        db_connected = False
        mongo_client = None
        db = None
        sensor_collection = None
        device_status_collection = None

# === Konfigurasi MQTT ===
mqtt_broker = "90c69dacebc2450495a401b6550d787b.s1.eu.hivemq.cloud" # Contoh: f6edeb4adb7c402ca7291dd7ef4d8fc5.s1.eu.hivemq.cloud
mqtt_port = 8883 # Port SSL/TLS
mqtt_user = "smarthome_flask_server" # <-- HARUS SAMA DENGAN USERNAME YG DISET DI HIVE MQ
mqtt_password = "Smarthome22" # <-- HARUS SAMA DENGAN PASSWORD YG DISET DI HIVE MQ
mqtt_client_id = "Flask_SmartHome_Server_001"
mqtt_topic_sub_mesh_sensor = "starswechase/sungai/mesh_sensor_data"
mqtt_topic_pub_lampu = "starswechase/sungai/control/lampu"
mqtt_topic_pub_kipas = "starswechase/sungai/control/kipas"

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=mqtt_client_id)
mqtt_connected = False

# Global status, akan diupdate oleh data dari MQTT
# Perlu diperbarui untuk menyimpan status per 'device_id' (Node1, Node2, dll.)
current_device_status_global = {
    "Node1_lampu": "OFF",
    "Node1_kipas": "OFF",
    "Node1_lux": 0,
    "Node1_temp": 0,
    "Node1_kelembaban": 0,
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Tambahkan entri untuk node lain jika ada, e.g., "Node2_lampu", "Node2_lux", dll.
}

def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        print("[MQTT] Connected to broker!")
        client.subscribe(mqtt_topic_sub_mesh_sensor) # Berlangganan topik data sensor dari Gateway
        client.subscribe(mqtt_topic_pub_lampu) # Tetap berlangganan untuk memantau jika ada publisher lain
        client.subscribe(mqtt_topic_pub_kipas) # Tetap berlangganan untuk memantau jika ada publisher lain
        mqtt_connected = True
    else:
        print(f"[MQTT] Failed to connect, return code: {rc}")
        mqtt_connected = False

def on_message(client, userdata, msg):
    global db_connected, sensor_collection, current_device_status_global, device_status_collection
    try:
        payload = json.loads(msg.payload.decode())
        payload["timestamp"] = datetime.now()
        payload["source"] = "mesh_sensor" # Menandakan ini data dari jaringan mesh

        # Data sensor dari mesh akan memiliki 'device_id' di payload
        device_id = payload.get("device_id", "unknown_node") 
        
        if db_connected and sensor_collection is not None:
            sensor_collection.insert_one(payload)
            print(f"[MongoDB] Mesh sensor data from {device_id} inserted.")
        else:
            print("[MongoDB] Not connected or sensor_collection not available, mesh sensor data not saved.")
        
        # Update current_device_status_global dengan data sensor terbaru per device_id
        current_device_status_global.update({
            f"{device_id}_lux": payload.get("lux", current_device_status_global.get(f"{device_id}_lux", "N/A")),
            f"{device_id}_temp": payload.get("suhu", payload.get("temperature", current_device_status_global.get(f"{device_id}_temp", "N/A"))),
            f"{device_id}_kelembaban": payload.get("kelembaban", payload.get("humidity", current_device_status_global.get(f"{device_id}_kelembaban", "N/A"))),
            "timestamp": payload["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        })

        # Jika pesan adalah respons dari perintah kontrol (misal dari Gateway setelah berhasil mengontrol device)
        # Anda bisa menambahkan logika untuk memperbarui status lampu/kipas di current_device_status_global
        # dan di database 'device_status_collection'
        if msg.topic == mqtt_topic_pub_lampu or msg.topic == mqtt_topic_pub_kipas:
            # Perlu diperbarui agar sesuai dengan format pesan yang dikirim dari Gateway
            # Jika Gateway mengirim payload { "device": "lampu", "state": "ON", "target_node_id": "Node1" }
            target_node_id_from_mqtt = payload.get("target_node_id")
            device_type_from_mqtt = payload.get("device")
            state_from_mqtt = payload.get("state")

            if target_node_id_from_mqtt and device_type_from_mqtt and state_from_mqtt:
                key = f"{target_node_id_from_mqtt}_{device_type_from_mqtt}"
                current_device_status_global[key] = state_from_mqtt

                if db_connected and device_status_collection is not None:
                    device_status_collection.update_one(
                        {"device": key},
                        {"$set": {"state": state_from_mqtt, "last_updated": datetime.now()}},
                        upsert=True
                    )
                    print(f"[MongoDB] Device status {key} updated to {state_from_mqtt} in DB.")
        
        print(f"[MQTT] Message processed. Topic: {msg.topic}")

    except json.JSONDecodeError:
        print(f"[MQTT] Error: Invalid JSON payload: {msg.payload.decode()}")
    except Exception as e:
        print(f"[MQTT] Error processing message: {e}")

def start_mqtt_loop():
    try:
        mqtt_client.tls_set() 
        mqtt_client.username_pw_set(mqtt_user, mqtt_password) 

        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.connect(mqtt_broker, mqtt_port, 60)
        mqtt_client.loop_forever() 
    except Exception as e:
        print(f"[MQTT] Failed to connect or start loop: {e}")

mqtt_thread = threading.Thread(target=start_mqtt_loop)
mqtt_thread.daemon = True 

app = Flask(__name__)
with app.app_context():
    connect_to_mongodb()
    mqtt_thread.start()
    print(f"[MQTT] Attempting to connect to broker {mqtt_broker}:{mqtt_port} in a separate thread...")

def get_current_device_status_from_db_reliable():
    local_current_status = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # Inisialisasi dengan N/A untuk semua node yang diharapkan
        "Node1_lampu": "N/A", "Node1_kipas": "N/A", 
        "Node1_lux": "N/A", "Node1_temp": "N/A", "Node1_kelembaban": "N/A",
        # Tambahkan Node2, Node3, dst.
    }

    if db_connected and device_status_collection is not None:
        try:
            # Ambil semua status perangkat dari koleksi device_status
            device_docs = device_status_collection.find({})
            for doc in device_docs:
                local_current_status[doc["device"]] = doc["state"]
        except Exception as e:
            print(f"[MongoDB] Error fetching device control status from DB: {e}")

    if db_connected and sensor_collection is not None:
        try:
            # Ambil data sensor terbaru untuk setiap device_id
            distinct_device_ids = sensor_collection.distinct("device_id")
            for device_id in distinct_device_ids:
                latest_sensor_doc = sensor_collection.find_one({"device_id": device_id}, sort=[("timestamp", -1)])
                if latest_sensor_doc:
                    local_current_status[f"{device_id}_lux"] = latest_sensor_doc.get("lux", "N/A")
                    local_current_status[f"{device_id}_temp"] = latest_sensor_doc.get("suhu", latest_sensor_doc.get("temperature", "N/A"))
                    local_current_status[f"{device_id}_kelembaban"] = latest_sensor_doc.get("kelembaban", latest_sensor_doc.get("humidity", "N/A"))
                    if isinstance(latest_sensor_doc.get("timestamp"), datetime):
                        local_current_status["timestamp"] = latest_sensor_doc["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    elif latest_sensor_doc.get("timestamp"):
                        local_current_status["timestamp"] = latest_sensor_doc["timestamp"]
        except Exception as e:
            print(f"[MongoDB] Error fetching latest sensor data from DB: {e}")
    
    return local_current_status


@app.route("/")
def index():
    return "✅ MQTT + Flask Server is Active (with Mesh Gateway)"

@app.route("/data")
def get_data():
    global current_device_status_global, sensor_collection, device_status_collection
    
    current_status_retrieved = get_current_device_status_from_db_reliable()
    current_device_status_global.update(current_status_retrieved)

    data_to_send = [current_device_status_global] 

    if db_connected and sensor_collection is not None:
        try:
            historical_sensor_data = list(sensor_collection.find().sort("timestamp", -1).limit(200)) # Sesuaikan limit
            
            for d in historical_sensor_data:
                d["_id"] = str(d["_id"]) 
                if isinstance(d.get("timestamp"), datetime):
                    d["timestamp"] = d["timestamp"].isoformat()
                data_to_send.append(d)
            
            print(f"[Flask] Responding with DB data. Current status (first 500 chars): {str(current_device_status_global)[:500]}")
            return jsonify(data_to_send)

        except Exception as e:
            print(f"[Flask] Error retrieving historical data from MongoDB: {e}. Returning dummy data.")
            # Dummy data logic adjusted for mesh, should include device_id
            dummy_data = []
            for i in range(10):
                timestamp = datetime.now() - timedelta(minutes=(9 - i) * 5)
                dummy_data.append({
                    "_id": str(i), "timestamp": timestamp.isoformat(),
                    "daya": random.randint(50, 200), "suhu": round(random.uniform(25.0, 30.0), 1),
                    "kelembaban": random.randint(40, 70), "lux": random.randint(50, 1000),
                    "source": "dummy", "device_id": "Node1" # Tambahkan device_id
                })
            return jsonify([current_device_status_global] + dummy_data)
    else:
        print("[Flask] MongoDB not connected or collection not available. Returning dummy data.")
        dummy_status_fallback = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Node1_lampu": random.choice(["ON", "OFF"]),
            "Node1_kipas": random.choice(["ON", "OFF"]),
            "Node1_lux": random.randint(100, 800),
            "Node1_temp": round(random.uniform(24.0, 29.5), 1),
            "Node1_kelembaban": random.randint(45, 65)
        }
        dummy_sensor_data = []
        for i in range(10):
            timestamp = datetime.now() - timedelta(minutes=(9 - i) * 5)
            dummy_sensor_data.append({
                "_id": str(i), "timestamp": timestamp.isoformat(),
                "daya": random.randint(50, 200), "suhu": round(random.uniform(25.0, 30.0), 1),
                "kelembaban": random.randint(40, 70), "lux": random.randint(50, 1000),
                "source": "dummy", "device_id": "Node1" # Tambahkan device_id
            })
        return jsonify([dummy_status_fallback] + dummy_sensor_data)


@app.route("/control/<device>/<state>/<target_node_id>")
def control_device(device, state, target_node_id):
    global current_device_status_global, device_status_collection
    state = state.upper()

    # Pastikan target_node_id diberikan dan sesuai dengan node yang ada
    if device in ["lampu", "kipas"] and state in ["ON", "OFF"] and target_node_id:
        
        # Perbarui status di MongoDB untuk device spesifik pada node spesifik
        db_key = f"{target_node_id}_{device}"
        if db_connected and device_status_collection is not None:
            try:
                device_status_collection.update_one(
                    {"device": db_key},
                    {"$set": {"state": state, "last_updated": datetime.now()}},
                    upsert=True
                )
                print(f"[MongoDB] Device {db_key} status updated to {state} in DB.")
                
                current_device_status_global[db_key] = state

            except Exception as e:
                print(f"[MongoDB] Error updating device status in DB: {e}. Internal status updated only.")
                current_device_status_global[db_key] = state 
        else:
            print("[MongoDB] Not connected or collection not available. Updating internal status only.")
            current_device_status_global[db_key] = state

        # Publikasikan perintah ke MQTT, tambahkan target_node_id di payload
        payload = json.dumps({"device": device, "state": state, "target_node_id": target_node_id})
        if mqtt_connected:
            if device == "lampu":
                mqtt_client.publish(mqtt_topic_pub_lampu, payload)
                print(f"[MQTT] Published command: {payload} to {mqtt_topic_pub_lampu}")
            elif device == "kipas":
                mqtt_client.publish(mqtt_topic_pub_kipas, payload)
                print(f"[MQTT] Published command: {payload} to {mqtt_topic_pub_kipas}")
        else:
            print(f"[MQTT] Broker not connected, command not published (simulated).")
        
        return jsonify({"status": "sent", "device": db_key, "current_state": current_device_status_global.get(db_key, "N/A")})
    
    return jsonify({"status": "error", "message": "Invalid command or missing target_node_id"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)