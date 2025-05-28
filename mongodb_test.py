from pymongo import MongoClient

# Ganti <username> dan <password> sesuai MongoDB Atlas kamu
uri = ("mongodb+srv://smarthome:smarthome99@cluster0.kaomhbl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

try:
    client = MongoClient(uri)
    db = client["smart_home"]
    collection = db["sensor_data"]

    # Contoh data sensor
    data = {
        "sensor_id": "S1",
        "suhu": 27.5,
        "kelembaban": 65,
        "timestamp": "2025-05-24T15:30:00"
    }

    result = collection.insert_one(data)
    print("✅ Data berhasil ditambahkan, ID:", result.inserted_id)

except Exception as e:
    print("❌ Gagal konek MongoDB:", e)
