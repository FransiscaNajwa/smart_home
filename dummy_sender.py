import random
import time
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")
if not db_password:
    raise ValueError("DB_PASSWORD tidak ditemukan di variabel lingkungan")

uri = f"mongodb+srv://smarthome:{db_password}@cluster0.kaomhbl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

def generate_dummy_data(num_records=10):
    try:
        mongo_client = MongoClient(uri)
        db = mongo_client["smarthomee"]
        collection = db["iot_data"]
    except Exception as e:
        print(f"Error saat menghubungkan ke MongoDB: {e}")
        return False

    base_time = int(time.time() * 1000)
    dummy_data = []

    for i in range(num_records):
        timestamp = base_time - (i * 5000)

        # Kondisi lampu dan arus
        kondisi_lampu = random.choice([True, False])
        status_lampu = "ON" if kondisi_lampu else "OFF"
        arus_lampu = round(random.uniform(0.01, 0.1), 3) if kondisi_lampu else 0.0
        watt_lampu = round(5 * arus_lampu, 3)  # Tegangan 5V x arus

        lampu_data = {
            "device": "lampu",
            "kondisi_lampu": kondisi_lampu,
            "status": status_lampu,
            "arus_lampu": arus_lampu,
            "watt": watt_lampu,
            "timestamp": timestamp,
            "received_at": timestamp + 100
        }
        dummy_data.append(lampu_data)

        # Kondisi kipas dan arus
        kondisi_kipas = random.choice([True, False])
        status_kipas = "ON" if kondisi_kipas else "OFF"
        arus_kipas = round(random.uniform(0.1, 0.5), 3) if kondisi_kipas else 0.0
        watt_kipas = round(5 * arus_kipas, 3)

        kipas_data = {
            "device": "kipas",
            "kondisi_kipas": kondisi_kipas,
            "status": status_kipas,
            "arus_kipas": arus_kipas,
            "watt": watt_kipas,
            "timestamp": timestamp,
            "received_at": timestamp + 100
        }
        dummy_data.append(kipas_data)

    try:
        collection.insert_many(dummy_data)
        print(f"Berhasil menyisipkan {len(dummy_data)} data dummy ke MongoDB")
        return True
    except Exception as e:
        print(f"Error saat menyisipkan data dummy: {e}")
        return False

if __name__ == "__main__":
    generate_dummy_data(20)