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
import threading
import pytz
from queue import Queue

# Inisialisasi Flask dan CORS
app = Flask(__name__)
CORS(app)

# ======== Konfigurasi MQTT HiveMQ Cloud ========
MQTT_BROKER = "8bda2df24fea4d2c9aadeb89eedd2738.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.webclient.1749548766220"
MQTT_PASSWORD = "1uBpWUE9<:jAq5>6d#bY"
MQTT_CONTROL_TOPIC_RELAY_ON_OFF = "iot/perintah/relay_on_off"
MQTT_CONTROL_TOPIC_RELAY_LAMPU = "iot/perintah/relay_lampu"

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

uri = f"mongodb+srv://alfarrelmahardika:Z.iLkvVg7Ep6!uP@cluster0.lnbl9.mongodb.net/"
mongo_client = MongoClient(uri)
db = mongo_client["manajemen_listrik"]
source_collection = db["kipas_dan_lampu"]
target_collection = db["kipas_dan_lampu_combined"]

# Buffer untuk menyimpan dokumen sementara
doc_buffer = Queue()
buffer_lock = threading.Lock()

# Fungsi untuk menggabungkan dua dokumen
def combine_documents(lampu_doc, kipas_doc):
    try:
        # Parse timestamps
        ts_lampu = datetime.strptime(lampu_doc["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)
        ts_kipas = datetime.strptime(kipas_doc["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)

        # Buat dokumen gabungan
        combined_doc = {
            "id": str(uuid.uuid4()),
            "relay_kipas": kipas_doc["relay"] == 0,  # 0=true(ON), 1=false(OFF)
            "relay_lampu": lampu_doc["relay"] == 0,  # 0=true(ON), 1=false(OFF)
            "watt_kipas": float(kipas_doc["watt"]),
            "watt_lampu": float(lampu_doc["watt"]),
            "timestamp_kipas": ts_kipas,
            "timestamp_lampu": ts_lampu
        }

        # Insert ke koleksi target
        target_collection.insert_one(combined_doc)
        print(f"Inserted combined document: {combined_doc['id']}")
    except Exception as e:
        print(f"Error combining documents {lampu_doc['_id']}, {kipas_doc['_id']}: {e}")

# Fungsi untuk memantau change stream
def watch_collection():
    try:
        with source_collection.watch() as stream:
            for change in stream:
                if change["operationType"] == "insert":
                    doc = change["fullDocument"]
                    with buffer_lock:
                        doc_buffer.put(doc)

                        # Cek apakah ada dua dokumen untuk digabung
                        if doc_buffer.qsize() >= 2:
                            doc1 = doc_buffer.get()
                            doc2 = doc_buffer.get()

                            # Tentukan lampu dan kipas
                            lampu_doc = doc1 if doc1["device_id"] == 1 else doc2
                            kipas_doc = doc2 if doc2["device_id"] == 2 else doc1

                            if lampu_doc["device_id"] == 1 and kipas_doc["device_id"] == 2:
                                combine_documents(lampu_doc, kipas_doc)
                            else:
                                print(f"Invalid pair: {doc1['_id']}, {doc2['_id']}")
                                # Kembalikan ke buffer jika urutan salah
                                doc_buffer.put(doc1)
                                doc_buffer.put(doc2)
    except Exception as e:
        print(f"Error in change stream: {e}")

# Jalankan change stream di thread terpisah
threading.Thread(target=watch_collection, daemon=True).start()

# ======== ROUTE UTAMA ========
@app.route('/control', methods=['GET', 'POST'])
def control_device():
    if request.method == 'POST':
        data = request.json
        device = data.get("device")

        if device not in ["kipas", "lampu"]:
            return jsonify({"status": "error", "message": "Device harus 'kipas' atau 'lampu'"}), 400

        # Ambil status terbaru dari MongoDB
        latest = target_collection.find().sort("timestamp_lampu", -1).limit(1)
        latest_data = next(latest, None)
        if not latest_data:
            return jsonify({"status": "error", "message": "Tidak ada data status terbaru"}), 500

        # Tentukan status saat ini dan kebalikannya
        current_state = latest_data["relay_kipas"] if device == "kipas" else latest_data["relay_lampu"]
        payload = "0" if not current_state else "1"  # 0=ON(true), 1=OFF(false)

        # Tentukan topik MQTT
        topic = MQTT_CONTROL_TOPIC_RELAY_ON_OFF if device == "kipas" else MQTT_CONTROL_TOPIC_RELAY_LAMPU
        result = mqtt_client.publish(topic, payload)

        if result[0] == 0:
            return jsonify({"status": "success", "device": device, "topic": topic, "payload": payload})
        else:
            return jsonify({"status": "error", "message": "MQTT publish gagal"}), 500

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
        raw = list(target_collection.find().sort("timestamp_lampu", -1).limit(100))
        out = []
        for r in raw:
            out.append({
                "device": "kipas",
                "timestamp": r["timestamp_kipas"].isoformat(),
                "status": "ON" if r["relay_kipas"] else "OFF",
                "arus_kipas": r["watt_kipas"] / 5,
                "watt": r["watt_kipas"]
            })
            out.append({
                "device": "lampu",
                "timestamp": r["timestamp_lampu"].isoformat(),
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
        tariff = float(request.args.get("tariff", 1500))
        raw = list(target_collection.find())

        if not raw:
            return jsonify({"status": "error", "message": "Tidak ada data di MongoDB"}), 400

        data = []
        for r in raw:
            if "timestamp_lampu" in r and r["timestamp_lampu"] and "watt_lampu" in r:
                data.append({
                    "device": "lampu",
                    "timestamp": r["timestamp_lampu"],
                    "watt": r["watt_lampu"]
                })
            if "timestamp_kipas" in r and r["timestamp_kipas"] and "watt_kipas" in r:
                data.append({
                    "device": "kipas",
                    "timestamp": r["timestamp_kipas"],
                    "watt": r["watt_kipas"]
                })

        if not data:
            return jsonify({"status": "error", "message": "Tidak ada data valid dengan timestamp"}), 400

        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors='coerce')
        if df["timestamp"].isna().any():
            print("Warning: Some timestamps are invalid and will be dropped")
            df = df.dropna(subset=["timestamp"])
        if df.empty:
            return jsonify({"status": "error", "message": "No valid timestamp data after parsing"}), 400

        df = df.sort_values("timestamp")
        df["duration"] = df.groupby("device")["timestamp"].diff().dt.total_seconds().fillna(0)
        df["energy_kwh"] = (df["watt"] * df["duration"] / 60)/ 1000
        df["date"] = df["timestamp"].dt.date

        daily = df.groupby("date")["energy_kwh"].sum().reset_index()
        daily["timestamp"] = pd.to_datetime(daily["date"]).dt.tz_localize("UTC")
        total_energy = daily["energy_kwh"].sum()
        total_cost = total_energy * tariff

        return jsonify({
            "status": "success",
            "daily_summary": daily[["timestamp", "energy_kwh"]].to_dict(orient="records"),
            "total_energy_kwh": float(total_energy),
            "total_cost": float(total_cost)
        })
    except Exception as e:
        print(f"Error in get_cost_summary: {str(e)}")
        return jsonify({"status": "error", "message": f"Gagal hitung rekap: {str(e)}"}), 500

# ======== RUN SERVER ========
if __name__ == '__main__':
    app.run(debug=True)