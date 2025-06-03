import os
import json
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from pymongo import MongoClient
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

MQTT_BROKER = "68c1b8e40d134f6c898d4d31b1d85940.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.webclient.1748991571679"
MQTT_PASSWORD = "kM7%jF$Z&AX<rp2fN01w"  # Ganti dengan password HiveMQ
MQTT_CLIENT_ID = "MicroPython_Sensor_001"
MQTT_SENSOR_TOPIC = "smarthome_data"
MQTT_CONTROL_TOPIC = "smarthome_control"

db_password = os.getenv("DB_PASSWORD")
mongo_uri = f"mongodb+srv://smarthome:{db_password}@cluster0.kaomhbl.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(mongo_uri)
db = client["smarthomee"]
collection = db["iot_data"]

app = Flask(__name__)

def parse_timestamp(ts):
    if isinstance(ts, (int, float)):
        return datetime.utcfromtimestamp(ts / 1000)
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None

def validate_required_fields(data, required_fields):
    missing = [field for field in required_fields if field not in data]
    if missing:
        print(f"❌ Data tidak memiliki kunci yang diperlukan: {missing}, data: {data}")
        return False
    return True

def sanitize_data(data):
    data.setdefault("kondisi_lampu", False if data.get("device") == "lampu" else None)
    data.setdefault("arus_lampu", 0.0 if data.get("device") == "lampu" else None)
    data.setdefault("kondisi_kipas", False if data.get("device") == "kipas" else None)
    data.setdefault("arus_kipas", 0.0 if data.get("device") == "kipas" else None)

    data["watt"] = round(5 * (data.get("arus_lampu", 0) + data.get("arus_kipas", 0)), 3)
    return data

# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker")
        client.subscribe(MQTT_SENSOR_TOPIC)
        client.subscribe(MQTT_CONTROL_TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)

        required_fields = ["device", "timestamp", "received_at"]
        if not validate_required_fields(data, required_fields):
            return

        data = sanitize_data(data)

        if "status" not in data:
            data["status"] = "ON" if data.get("kondisi_lampu") or data.get("kondisi_kipas") else "OFF"

        collection.insert_one(data)
        print(f"Data inserted: {data}")

    except Exception as e:
        print(f"Error processing MQTT message: {e}")

mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
mqtt_client.tls_set()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
mqtt_client.loop_start()

@app.route('/control', methods=['GET', 'POST'])
def control_device():
    if request.method == 'POST':
        data = request.json
        device = data.get("device")
        state = data.get("state")
        if device and state:
            topic = f"smart_home/control/{device}"
            result = mqtt_client.publish(topic, state)
            if result[0] == 0:
                return jsonify({"status": "success", "device": device, "state": state})
            else:
                return jsonify({"status": "error", "message": "Failed to publish"}), 500
        else:
            return jsonify({"status": "error", "message": "Invalid request"}), 400

    elif request.method == 'GET':
        action = request.args.get("action")
        if action == "data":
            raw_data = list(collection.find().sort("timestamp", -1).limit(100))
            for item in raw_data:
                item["_id"] = str(item["_id"])
                dt = parse_timestamp(item.get("timestamp"))
                item["timestamp"] = dt.isoformat() if dt else None
            return jsonify(raw_data)

        elif action == "cost_summary":
            period = request.args.get("period", "daily")
            tariff = float(request.args.get("tariff", 1500))
            now = datetime.utcnow()

            if period == "weekly":
                start = now - timedelta(days=7)
            elif period == "monthly":
                start = now - timedelta(days=30)
            elif period == "yearly":
                start = now - timedelta(days=365)
            else:
                start = now - timedelta(days=1)

            raw_data = list(collection.find({"timestamp": {"$gte": int(start.timestamp() * 1000)}}))
            if not raw_data:
                return jsonify({"total_energy_kwh": 0, "total_cost": 0, "daily_summary": []})

            for item in raw_data:
                dt = parse_timestamp(item.get("timestamp"))
                item["timestamp"] = dt if dt else None

            df = pd.DataFrame(raw_data)
            if df.empty or "timestamp" not in df.columns or df["timestamp"].isnull().all():
                return jsonify({"total_energy_kwh": 0, "total_cost": 0, "daily_summary": []})

            df = df.dropna(subset=["timestamp"])
            df = df.sort_values("timestamp")
            df['duration_s'] = df['timestamp'].diff().dt.total_seconds().fillna(0)

            df['energy_kwh'] = (df['watt'] * df['duration_s'] / 3600) / 1000
            total_energy = df['energy_kwh'].sum()
            total_cost = total_energy * tariff

            daily_summary = df.groupby(df['timestamp'].dt.date).agg({'energy_kwh': 'sum'}).reset_index()
            daily_summary['timestamp'] = daily_summary['timestamp'].astype(str)  # Pastikan timestamp ada
            return jsonify({
                "total_energy_kwh": total_energy,
                "total_cost": total_cost,
                "daily_summary": daily_summary.to_dict('records')
            })

    return jsonify({"status": "error", "message": "Invalid action"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)