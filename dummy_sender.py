import random
from datetime import datetime, timedelta
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")
if not db_password:
    raise ValueError("DB_PASSWORD tidak ditemukan di variabel lingkungan")

uri = f"mongodb+srv://smarthome:{db_password}@cluster0.kaomhbl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

def generate_dummy_data(days=30, records_per_day=1440):  # 1440 = 24 hours * 60 minutes
    try:
        mongo_client = MongoClient(uri)
        db = mongo_client["manajemen_listrik"]
        collection = db["kipas_dan_lampu"]
    except Exception as e:
        print(f"❌ Gagal koneksi ke MongoDB: {e}")
        return False

    # Clear existing data (optional, comment out if not needed)
    collection.delete_many({})
    print("🧹 Koleksi dibersihkan sebelum menyisipkan data baru")

    dummy_data = []
    start_date = datetime(2025, 6, 10, 17,59, 0)  # End at June 11, 2025, 23:59
    total_records = days * records_per_day  # 30 * 1440 = 43,200

    # Track device state and duration to avoid rapid toggling
    kipas_state = False
    lampu_state = False
    kipas_state_duration = 0  # Minutes until state change
    lampu_state_duration = 0
    kipas_watt_base = 0.0  # Base wattage for smooth variation
    lampu_watt_base = 0.0

    for i in range(total_records):
        # Calculate timestamp (1 minute intervals, counting backward)
        minutes_offset = i
        timestamp = start_date - timedelta(minutes=minutes_offset)
        # Convert to WIB (UTC+7) for usage pattern logic
        wib_hour = (timestamp + timedelta(hours=7)).hour

        # Update kipas state
        if kipas_state_duration <= 0:
            # Kipas: More likely ON during 8 AM–10 PM WIB
            if 8 <= wib_hour <= 22:
                kipas_prob = 0.75  # 75% chance ON
            else:
                kipas_prob = 0.25  # 25% chance ON
            kipas_state = random.random() < kipas_prob
            # Set duration for state (15–60 minutes)
            kipas_state_duration = random.randint(15, 60)
            # Reset base wattage when state changes to ON
            if kipas_state:
                kipas_watt_base = random.uniform(20, 50)
        kipas_state_duration -= 1

        # Update lampu state
        if lampu_state_duration <= 0:
            # Lampu: More likely ON during 6 PM–11 PM WIB
            if 18 <= wib_hour <= 23:
                lampu_prob = 0.85  # 85% chance ON
            elif 6 <= wib_hour < 18:
                lampu_prob = 0.25  # 25% chance ON
            else:
                lampu_prob = 0.1   # 10% chance ON
            lampu_state = random.random() < lampu_prob
            # Set duration for state (15–60 minutes)
            lampu_state_duration = random.randint(15, 60)
            # Reset base wattage when state changes to ON
            if lampu_state:
                lampu_watt_base = random.uniform(5, 20)
        lampu_state_duration -= 1

        # Power consumption with slight variation
        watt_kipas = round(kipas_watt_base + random.uniform(-2, 2), 3) if kipas_state else 0.0
        watt_lampu = round(lampu_watt_base + random.uniform(-1, 1), 3) if lampu_state else 0.0
        # Ensure non-negative wattage
        watt_kipas = max(watt_kipas, 0.0)
        watt_lampu = max(watt_lampu, 0.0)

        doc = {
            "id": f"dummy-{i}",
            "relay_kipas": kipas_state,
            "relay_lampu": lampu_state,
            "watt_kipas": watt_kipas,
            "watt_lampu": watt_lampu,
            "timestamp_kipas": timestamp,
            "timestamp_lampu":(timestamp + timedelta(seconds=1))
        }
        dummy_data.append(doc)

        # Batch insert every 10,000 records to manage memory
        if len(dummy_data) >= 10000:
            try:
                collection.insert_many(dummy_data)
                print(f"✅ Menyisipkan {len(dummy_data)} data ke MongoDB")
                dummy_data = []
            except Exception as e:
                print(f"❌ Error saat menyisipkan data: {e}")
                return False

    # Insert remaining data
    if dummy_data:
        try:
            collection.insert_many(dummy_data)
            print(f"✅ Menyisipkan {len(dummy_data)} data ke MongoDB")
        except Exception as e:
            print(f"❌ Error saat menyisipkan data: {e}")
            return False

    print(f"✅ Berhasil menyisipkan total {total_records} data dummy ke MongoDB")
    return True

if __name__ == "__main__":
    generate_dummy_data(days=30, records_per_day=1440)