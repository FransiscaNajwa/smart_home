import os
import ssl
import json
import uuid
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

# Inisialisasi Flask dan CORS
app = Flask(__name__)
CORS(app)

# ======== Konfigurasi MQTT HiveMQ Cloud ========
MQTT_BROKER = "8acc9ffec16d43469734fd033e74dac1.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.webclient.1749620447915"
MQTT_PASSWORD = "#2Y4puH3%?qa:GSj1rAV"
MQTT_CONTROL_TOPIC_KIPAS = "smarthome/command/kipas"
MQTT_CONTROL_TOPIC_LAMPU = "smarthome/command/lampu"

# Setup MQTT client
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLS)
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# ======== Koneksi MongoDB ========
load_dotenv()
db_password = os.getenv("DB_PASSWORD")
if not db_password:
    raise ValueError("DB_PASSWORD tidak ditemukan di .env")

uri = f"mongodb+srv://smarthome:{db_password}@cluster0.kaomhbl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
mongo_client = MongoClient(uri)
db = mongo_client["manajemen_listrik"]
collection = db["kipas_dan_lampu"]

# ======== ROUTE UTAMA ========
@app.route('/control', methods=['GET', 'POST'])
def control_device():
    if request.method == 'POST':
        data = request.json
        device = data.get("device")
        state = data.get("state")

        if device not in ["kipas", "lampu"]:
            return jsonify({"status": "error", "message": "Device harus 'kipas' atau 'lampu'"}), 400
        if state is None:
            return jsonify({"status": "error", "message": "State tidak boleh kosong"}), 400

        payload = {
            "id": str(uuid.uuid4()),
            "status": state.lower() == "on",
            "timestamp": datetime.now().isoformat()
        }

        topic = MQTT_CONTROL_TOPIC_KIPAS if device == "kipas" else MQTT_CONTROL_TOPIC_LAMPU
        result = mqtt_client.publish(topic, json.dumps(payload))

        if result[0] == 0:
            return jsonify({"status": "success", "device": device, "topic": topic, "payload": payload})
        else:
            return jsonify({"status": "error", "message": "MQTT publish failed"}), 500

    elif request.method == 'GET':
        action = request.args.get('action')
        if action == 'data':
            return get_sensor_data()
        elif action == 'cost_summary':
            return get_cost_summary()
        else:
            return jsonify({"status": "error", "message": "Action tidak dikenali"}), 400

# ======== Fungsi untuk GET /control?action=data ========
def get_sensor_data():
    try:
        raw = list(collection.find().sort("timestamp_kipas", -1).limit(100))
        out = []
        for r in raw:
            out.append({
                "device": "kipas",
                "timestamp": r["timestamp_kipas"],
                "status": "ON" if r["relay_kipas"] else "OFF",
                "arus_kipas": r["watt_kipas"] / 5,
                "watt": r["watt_kipas"]
            })
            out.append({
                "device": "lampu",
                "timestamp": r["timestamp_lampu"],
                "status": "ON" if r["relay_lampu"] else "OFF",
                "arus_lampu": r["watt_lampu"] / 5,
                "watt": r["watt_lampu"]
            })
        return jsonify(out)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Gagal ambil data: {e}"}), 500

# ======== Fungsi untuk GET /control?action=cost_summary ========
def get_cost_summary():
    try:
        period = request.args.get("period", "weekly")
        tariff = float(request.args.get("tariff", 1500))
        days_map = {"weekly": 7, "monthly": 30, "yearly": 365}
        days = days_map.get(period, 1)
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Fetch data from MongoDB, ensuring both timestamps exist
        raw = list(collection.find({
            "$and": [
                {"timestamp_kipas": {"$gte": cutoff, "$exists": True, "$ne": None}},
                {"timestamp_lampu": {"$gte": cutoff, "$exists": True, "$ne": None}}
            ]
        }))
        
        if not raw:
            return jsonify({
                "status": "error",
                "message": "No valid data found for the specified period"
            }), 400

        data = []
        for r in raw:
            # Process kipas data
            if "timestamp_kipas" in r and r["timestamp_kipas"] and "watt_kipas" in r:
                try:
                    # Validate timestamp format
                    pd.to_datetime(r["timestamp_kipas"])  # Test conversion
                    data.append({
                        "device": "kipas",
                        "timestamp": r["timestamp_kipas"],
                        "watt": r["watt_kipas"]
                    })
                except (ValueError, TypeError):
                    continue  # Skip invalid timestamp
            # Process lampu data
            if "timestamp_lampu" in r and r["timestamp_lampu"] and "watt_lampu" in r:
                try:
                    pd.to_datetime(r["timestamp_lampu"])  # Test conversion
                    data.append({
                        "device": "lampu",
                        "timestamp": r["timestamp_lampu"],
                        "watt": r["watt_lampu"]
                    })
                except (ValueError, TypeError):
                    continue  # Skip invalid timestamp

        if not data:
            return jsonify({
                "status": "error",
                "message": "No valid data with timestamps found for the specified period"
            }), 400

        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
        df["duration"] = df.groupby("device")["timestamp"].diff().dt.total_seconds().fillna(0)
        df["energy_kwh"] = (df["watt"] * df["duration"] / 3600) / 1000
        df["date"] = df["timestamp"].dt.date

        daily = df.groupby("date")["energy_kwh"].sum().reset_index()
        daily["timestamp"] = pd.to_datetime(daily["date"])

        return jsonify({
            "status": "success",
            "daily_summary": daily.to_dict(orient="records"),
            "total_energy_kwh": float(df["energy_kwh"].sum()),
            "total_cost": float(df["energy_kwh"].sum() * tariff)
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Gagal hitung rekap: {str(e)}"
        }), 500

# ======== RUN SERVER ========
if __name__ == '__main__':
    app.run(debug=True)