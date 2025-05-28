from flask import Flask, jsonify
import paho.mqtt.client as mqtt
from pymongo import MongoClient
from datetime import datetime, timedelta
import json, random, threading

# === Konfigurasi MongoDB ===
# Pastikan URI ini sudah benar dan Anda memiliki akses yang tepat
mongo_uri = "mongodb+srv://smarthome:smarthome99@cluster0.kaomhbl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
MONGO_DB_NAME = "smart_home"
SENSOR_COLLECTION_NAME = "sensor_data"
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
        # The ping command is a good way to check if the connection is active.
        mongo_client.admin.command("ping") 
        db = mongo_client[MONGO_DB_NAME]
        sensor_collection = db[SENSOR_COLLECTION_NAME]
        device_status_collection = db[DEVICE_STATUS_COLLECTION_NAME]
        db_connected = True
        print("[MongoDB] Connected successfully.")
        
        # Inisialisasi status lampu dan kipas di DB jika belum ada
        # Pastikan menggunakan key "state" untuk status, bukan "status" seperti di awal
        if device_status_collection.find_one({"device": "lampu"}) is None:
            device_status_collection.insert_one({"device": "lampu", "state": "OFF", "last_updated": datetime.now()})
            print("[MongoDB] Initial status for 'lampu' added.")
        if device_status_collection.find_one({"device": "kipas"}) is None:
            device_status_collection.insert_one({"device": "kipas", "state": "OFF", "last_updated": datetime.now()})
            print("[MongoDB] Initial status for 'kipas' added.")

    except Exception as e:
        print(f"[MongoDB] Connection failed: {e}")
        db_connected = False
        mongo_client = None
        db = None
        sensor_collection = None
        device_status_collection = None

# === Konfigurasi MQTT ===
mqtt_broker = "broker.hivemq.com"
mqtt_port = 1883
mqtt_topic_sub = "rumah/status" # Topik untuk menerima data sensor dari perangkat
mqtt_topic_pub = "rumah/control" # Topik untuk mengirim perintah ke perangkat
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
mqtt_connected = False

# current_device_status akan di-update dari DB, jadi tidak perlu default random di sini
# Ini hanya sebagai placeholder untuk inisialisasi awal. Akan di-overwrite dari DB.
current_device_status_global = {
    "lampu": "OFF",
    "kipas": "OFF",
    "lux": 0,
    "temp": 0,
    "kelembaban": 0,
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        print("[MQTT] Connected to broker!")
        client.subscribe(mqtt_topic_sub)
        mqtt_connected = True
    else:
        print(f"[MQTT] Failed to connect, return code: {rc}")
        mqtt_connected = False

def on_message(client, userdata, msg):
    global db_connected, sensor_collection, current_device_status_global # Gunakan global current_device_status_global
    try:
        payload = json.loads(msg.payload.decode())
        payload["timestamp"] = datetime.now()
        payload["daya"] = payload.get("daya", random.randint(50, 150)) # Fallback daya jika tidak ada dari hardware
        payload["source"] = "sensor" # Menandakan ini data dari sensor fisik

        if db_connected and sensor_collection is not None:
            sensor_collection.insert_one(payload)
            print("[MongoDB] Sensor data inserted from MQTT.")
        else:
            print("[MongoDB] Not connected or sensor_collection not available, sensor data not saved.")
        
        # Update current_device_status_global dengan data sensor terbaru
        current_device_status_global.update({
            "lux": payload.get("lux", current_device_status_global["lux"]),
            "temp": payload.get("suhu", payload.get("temperature", current_device_status_global["temp"])),
            "kelembaban": payload.get("kelembaban", payload.get("humidity", current_device_status_global["kelembaban"])),
            "timestamp": payload["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        })
        print(f"[MQTT] Sensor message processed.")
    except json.JSONDecodeError:
        print(f"[MQTT] Error: Invalid JSON payload: {msg.payload.decode()}")
    except Exception as e:
        print(f"[MQTT] Error processing message: {e}")

def start_mqtt_loop():
    try:
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.connect(mqtt_broker, mqtt_port, 60)
        mqtt_client.loop_forever() # Blocks, so it must be in a separate thread
    except Exception as e:
        print(f"[MQTT] Failed to connect or start loop: {e}")

mqtt_thread = threading.Thread(target=start_mqtt_loop)
mqtt_thread.daemon = True # Allows the main program to exit even if this thread is running


app = Flask(__name__)
# Pastikan koneksi DB dipanggil sebelum Flask routes atau bagian yang memerlukannya aktif
with app.app_context(): # Pastikan ini di dalam context aplikasi Flask jika ada isu threading/context
    connect_to_mongodb()
    mqtt_thread.start()
    print(f"[MQTT] Attempting to connect to broker {mqtt_broker}:{mqtt_port} in a separate thread...")


# Dummy fallback functions (digunakan hanya jika DB tidak terhubung atau error)
def generate_dummy_sensor_data_flask(num_entries=10):
    data = []
    for i in range(num_entries):
        timestamp = datetime.now() - timedelta(minutes=(num_entries - 1 - i) * 5)
        data.append({
            "_id": str(i),
            "timestamp": timestamp,
            "daya": random.randint(50, 200),
            "suhu": round(random.uniform(25.0, 30.0), 1),
            "kelembaban": random.randint(40, 70),
            "lux": random.randint(50, 1000),
            "source": "dummy" # Menandakan ini data dummy
        })
    return data

def get_current_device_status_from_db_reliable():
    # Fungsi ini akan selalu mencoba mengambil data dari DB jika terhubung,
    # atau memberikan default yang masuk akal jika tidak.
    local_current_status = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "lampu": "N/A", # Default N/A jika tidak bisa didapat dari DB
        "kipas": "N/A",
        "lux": "N/A",
        "temp": "N/A",
        "kelembaban": "N/A"
    }

    if db_connected and device_status_collection is not None:
        try:
            lampu_doc = device_status_collection.find_one({"device": "lampu"})
            kipas_doc = device_status_collection.find_one({"device": "kipas"})
            
            local_current_status["lampu"] = lampu_doc.get("state", "N/A") if lampu_doc else "N/A"
            local_current_status["kipas"] = kipas_doc.get("state", "N/A") if kipas_doc else "N/A"
        except Exception as e:
            print(f"[MongoDB] Error fetching device control status from DB: {e}")
            # Biarkan N/A jika ada error saat fetch

    if db_connected and sensor_collection is not None:
        try:
            latest_sensor_doc = sensor_collection.find_one(sort=[("timestamp", -1)])
            if latest_sensor_doc:
                local_current_status["lux"] = latest_sensor_doc.get("lux", "N/A")
                local_current_status["temp"] = latest_sensor_doc.get("suhu", latest_sensor_doc.get("temperature", "N/A"))
                local_current_status["kelembaban"] = latest_sensor_doc.get("kelembaban", latest_sensor_doc.get("humidity", "N/A"))
                if isinstance(latest_sensor_doc.get("timestamp"), datetime):
                    local_current_status["timestamp"] = latest_sensor_doc["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                elif latest_sensor_doc.get("timestamp"): # Jika sudah string tapi ada
                    local_current_status["timestamp"] = latest_sensor_doc["timestamp"]
        except Exception as e:
            print(f"[MongoDB] Error fetching latest sensor data from DB: {e}")
            # Biarkan N/A jika ada error saat fetch
    
    return local_current_status

@app.route("/")
def index():
    return "✅ MQTT + Flask Server is Active"

@app.route("/data")
def get_data():
    global current_device_status_global, sensor_collection, device_status_collection
    
    # Selalu ambil status terkini dari DB (atau fallback) saat endpoint ini diakses
    current_status_retrieved = get_current_device_status_from_db_reliable()
    
    # Update global status agar selalu mencerminkan apa yang terakhir diambil
    current_device_status_global.update(current_status_retrieved)

    data_to_send = [current_device_status_global] # Elemen pertama adalah status terkini

    if db_connected and sensor_collection is not None:
        try:
            historical_sensor_data = list(sensor_collection.find().sort("timestamp", -1).limit(200)) # Sesuaikan limit
            
            for d in historical_sensor_data:
                d["_id"] = str(d["_id"]) # Konversi ObjectId ke string
                if isinstance(d.get("timestamp"), datetime):
                    d["timestamp"] = d["timestamp"].isoformat()
                data_to_send.append(d)
            
            print(f"[Flask] Responding with DB data. Current status: {current_device_status_global}")
            return jsonify(data_to_send)

        except Exception as e:
            print(f"[Flask] Error retrieving historical data from MongoDB: {e}. Returning dummy data.")
            # Fallback jika ada error saat mengambil data historis, tapi status terkini tetap dari upaya DB
            dummy_sensor_data = generate_dummy_sensor_data_flask(10)
            for d in dummy_sensor_data:
                d["timestamp"] = d["timestamp"].isoformat()
            return jsonify([current_device_status_global] + dummy_sensor_data)
    else:
        print("[Flask] MongoDB not connected or collection not available. Returning dummy data.")
        # Jika DB tidak terhubung sama sekali, buat dummy status dan dummy historis
        dummy_status_fallback = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "lampu": random.choice(["ON", "OFF"]),
            "kipas": random.choice(["ON", "OFF"]),
            "lux": random.randint(100, 800),
            "temp": round(random.uniform(24.0, 29.5), 1),
            "kelembaban": random.randint(45, 65)
        }
        dummy_sensor_data = generate_dummy_sensor_data_flask(10)
        for d in dummy_sensor_data:
            d["timestamp"] = d["timestamp"].isoformat()
        return jsonify([dummy_status_fallback] + dummy_sensor_data)


@app.route("/control/<device>/<state>")
def control_device(device, state):
    global current_device_status_global, device_status_collection
    state = state.upper()

    if device in ["lampu", "kipas"] and state in ["ON", "OFF"]:
        if db_connected and device_status_collection is not None:
            try:
                # Update status di MongoDB
                device_status_collection.update_one(
                    {"device": device},
                    {"$set": {"state": state, "last_updated": datetime.now()}},
                    upsert=True
                )
                print(f"[MongoDB] Device {device} status updated to {state} in DB.")
                
                # Perbarui global current_device_status_global agar Streamlit mendapat feedback instan
                current_device_status_global[device] = state

            except Exception as e:
                print(f"[MongoDB] Error updating device status in DB: {e}. Internal status updated only.")
                current_device_status_global[device] = state # Update internal status if DB fails
        else:
            print("[MongoDB] Not connected or collection not available. Updating internal status only.")
            current_device_status_global[device] = state # Update internal status if DB not connected

        # Publikasikan perintah ke MQTT
        payload = json.dumps({"device": device, "state": state})
        if mqtt_connected:
            mqtt_client.publish(mqtt_topic_pub, payload)
            print(f"[MQTT] Published command: {payload} to {mqtt_topic_pub}")
        else:
            print(f"[MQTT] Broker not connected, command not published (simulated).")
        
        # Kembalikan status terbaru dari global variable yang sudah diupdate
        return jsonify({"status": "sent", "device": device, "current_state": current_device_status_global[device]})
    
    return jsonify({"status": "error", "message": "Invalid command"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)