from flask import Flask, jsonify, request
import paho.mqtt.client as mqtt
from pymongo import MongoClient
import json
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
import logging

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Memuat variabel lingkungan dari file .env
load_dotenv()

app = Flask(__name__)

# Ambil kata sandi dari variabel lingkungan
db_password = os.getenv("DB_PASSWORD")
if not db_password:
    logger.error("Error: DB_PASSWORD tidak ditemukan di variabel lingkungan")
    raise ValueError("DB_PASSWORD tidak ditemukan di variabel lingkungan")

# URI MongoDB Atlas
uri = f"mongodb+srv://smarthome:{db_password}@cluster0.kaomhbl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Konfigurasi MongoDB
try:
    mongo_client = MongoClient(uri)
    db = mongo_client["smart_home"]
    collection = db["iot_sensor"]
    logger.info("Berhasil terhubung ke MongoDB Atlas")
except Exception as e:
    logger.error(f"Error saat menghubungkan ke MongoDB: {e}")
    raise

# Konfigurasi MQTT
MQTT_BROKER = "6f820295b0364ee293a9a96c1f2457a6.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.webclient.1748687406394"
MQTT_PASSWORD = "K0p.D,9ErwiU!W51kS&n"
MQTT_SENSOR_TOPIC = "starswechase/sungai/data"  # Diselaraskan dengan Arduino
MQTT_CONTROL_TOPIC = "starswechase/sungai/control"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"Terhubung ke MQTT Broker dengan kode hasil: {rc}")
        client.subscribe(MQTT_SENSOR_TOPIC, qos=1)
        client.subscribe(f"{MQTT_CONTROL_TOPIC}/#", qos=1)  # Subscribe dengan wildcard
        logger.info(f"Subscribed ke {MQTT_SENSOR_TOPIC} dan {MQTT_CONTROL_TOPIC}/#")
    else:
        logger.warning(f"Koneksi gagal dengan kode: {rc}")

def on_disconnect(client, userdata, rc):
    logger.warning(f"Terputus dari MQTT Broker dengan kode: {rc}")
    if rc != 0:
        logger.info("Mencoba reconnect...")
        while True:
            try:
                client.reconnect()
                break
            except Exception as e:
                logger.error(f"Reconnect gagal: {e}")
                time.sleep(5)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        if msg.topic == MQTT_SENSOR_TOPIC:
            data["received_at"] = int(time.time() * 1000)
            collection.insert_one(data)
            logger.info(f"Data disimpan ke MongoDB: {data}")
        elif msg.topic.startswith(MQTT_CONTROL_TOPIC):
            logger.info(f"Perintah kontrol diterima: {data}")
    except json.JSONDecodeError:
        logger.error(f"Error: Pesan MQTT bukan JSON valid: {msg.payload.decode()}")
    except Exception as e:
        logger.error(f"Error saat memproses pesan: {e}")

# Setup klien MQTT
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
mqtt_client.tls_set(ca_certs=None, certfile=None, keyfile=None, cert_reqs=mqtt.ssl.CERT_REQUIRED, tls_version=mqtt.ssl.PROTOCOL_TLSv1_2, ciphers=None)
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
    mqtt_client.loop_start()
    logger.info("MQTT Client dimulai dan berjalan")
except Exception as e:
    logger.error(f"Error saat menghubungkan ke MQTT: {e}")
    raise

# Endpoint utama
@app.route('/')
def index():
    return jsonify({"message": "Flask MQTT to MongoDB Bridge"})

# Endpoint tunggal untuk semua aksi
@app.route('/api', methods=['GET', 'POST'])
def api():
    try:
        if request.method == 'GET':
            action = request.args.get('action', 'data')
            if action == 'data':
                limit = int(request.args.get('limit', 50))
                data = list(collection.find().sort("received_at", -1).limit(limit))
                for item in data:
                    item['_id'] = str(item['_id'])
                return jsonify(data)
            elif action == 'cost_summary':
                period = request.args.get('period', 'monthly')
                tariff = float(request.args.get('tariff', 1500))
                limit = int(request.args.get('limit', 50))
                now = datetime.now()
                if period == 'weekly':
                    start_date = now - timedelta(days=7)
                elif period == 'monthly':
                    start_date = now - relativedelta(months=1)
                elif period == 'yearly':
                    start_date = now - relativedelta(years=1)
                else:
                    return jsonify({"error": "Periode tidak valid"}), 400

                query = {"timestamp": {"$gte": int(start_date.timestamp() * 1000)}}
                data = list(collection.find(query).sort("timestamp", 1).limit(limit))
                if not data:
                    return jsonify({"total_energy_kwh": 0, "total_cost": 0, "daily_summary": []})

                df = pd.DataFrame(data)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
                df = df.dropna(subset=['timestamp'])
                if df.empty:
                    return jsonify({"total_energy_kwh": 0, "total_cost": 0, "daily_summary": []})

                df = df.sort_values('timestamp')
                df['power_w'] = 0
                df.loc[(df['device'] == 'ESP32') & (df['actuator_state'] == True), 'power_w'] = 5
                df.loc[(df['device'] == 'ESP8266') & (df['actuator_state'] == True), 'power_w'] = 10
                df['duration_h'] = df['timestamp'].diff().dt.total_seconds() / 3600
                df['duration_h'].fillna(0, inplace=True)
                df['duration_h'] = df['duration_h'].clip(lower=0)
                df['energy_kwh'] = df['power_w'] * df['duration_h'] / 1000
                df['cost'] = df['energy_kwh'] * tariff

                total_energy = df['energy_kwh'].sum()
                total_cost = df['cost'].sum()
                df['date'] = df['timestamp'].dt.date
                daily = df.groupby('date').agg({'energy_kwh': 'sum', 'cost': 'sum'}).reset_index()
                daily['date'] = daily['date'].astype(str)
                daily_summary = daily.to_dict(orient='records')

                return jsonify({
                    "period": period,
                    "total_energy_kwh": float(total_energy),
                    "total_cost": float(total_cost),
                    "daily_summary": daily_summary
                })
            else:
                return jsonify({"error": "Aksi GET tidak valid"}), 400

        elif request.method == 'POST':
            action = request.args.get('action', 'control')
            if action == 'control':
                data = request.get_json()
                if not data or 'device' not in data or 'actuator' not in data or 'state' not in data:
                    return jsonify({"error": "Data tidak valid"}), 400
                payload = json.dumps(data)
                mqtt_client.publish(MQTT_CONTROL_TOPIC, payload, qos=1)
                return jsonify({"message": f"Perintah untuk {data['device']} ({data['actuator']}) dikirim"})
            else:
                return jsonify({"error": "Aksi POST tidak valid"}), 400

    except Exception as e:
        logger.error(f"Gagal memproses permintaan: {str(e)}")
        return jsonify({"error": f"Gagal memproses permintaan: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)