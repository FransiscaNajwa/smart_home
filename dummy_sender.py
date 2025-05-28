# dummy_seeder.py
from pymongo import MongoClient
from datetime import datetime
import random
import time

# Konfigurasi MongoDB Cloud
mongo_uri = "mongodb+srv://smarthome:smarthome99@cluster0.kaomhbl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(mongo_uri)
db = client["smart_home"]
collection = db["sensor_data"]

print("🔁 Dummy seeder dimulai. Tekan Ctrl+C untuk berhenti.\n")

try:
    while True:
        data_dummy = {
            "node": random.choice(["lampu", "kipas"]),
            "lux": round(random.uniform(50, 300), 2),
            "temperature": round(random.uniform(25, 35), 1),
            "humidity": round(random.uniform(40, 70), 1),
            "lampu": random.choice(["ON", "OFF"]),
            "kipas": random.choice(["ON", "OFF"]),
            "daya": random.randint(50, 200),
            "timestamp": datetime.now()
        }

        collection.insert_one(data_dummy)
        print(f"[MongoDB] Dummy inserted: {data_dummy}")
        time.sleep(5)

except KeyboardInterrupt:
    print("\n❌ Seeder dihentikan.")
