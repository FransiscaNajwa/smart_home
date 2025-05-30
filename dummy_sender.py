import random
import time
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Memuat variabel lingkungan
load_dotenv()

# Ambil kata sandi dari variabel lingkungan
db_password = os.getenv("DB_PASSWORD")
if not db_password:
    raise ValueError("DB_PASSWORD tidak ditemukan di variabel lingkungan")

# URI MongoDB Atlas
uri = f"mongodb+srv://smarthome:{db_password}@cluster0.kaomhbl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

def generate_dummy_data(num_records=10):
    try:
        mongo_client = MongoClient(uri)
        db = mongo_client["smart_home"]
        collection = db["iot_sensor"]
    except Exception as e:
        print(f"Error saat menghubungkan ke MongoDB: {e}")
        return False

    base_time = int(time.time() * 1000)
    dummy_data = []

    for i in range(num_records):
        # Data untuk ESP32
        esp32_data = {
            "device": "ESP32",
            "lux": round(random.uniform(400, 600), 2),
            "voltage": round(random.uniform(3.0, 3.3), 2),
            "actuator": "LED",
            "actuator_state": random.choice([True, False]),
            "timestamp": base_time - (i * 5000),
            "received_at": base_time - (i * 5000) + 100
        }
        dummy_data.append(esp32_data)

        # Data untuk ESP8266
        esp8266_data = {
            "device": "ESP8266",
            "temperature": round(random.uniform(24, 27), 2),
            "humidity": round(random.uniform(55, 65), 2),
            "voltage": round(random.uniform(3.0, 3.3), 2),
            "actuator": "MOTOR",
            "actuator_state": random.choice([True, False]),
            "timestamp": base_time - (i * 5000),
            "received_at": base_time - (i * 5000) + 100
        }
        dummy_data.append(esp8266_data)

    try:
        collection.insert_many(dummy_data)
        print(f"Berhasil menyisipkan {len(dummy_data)} data dummy ke MongoDB")
        return True
    except Exception as e:
        print(f"Error saat menyisipkan data dummy: {e}")
        return False

if __name__ == "__main__":
    generate_dummy_data(20)