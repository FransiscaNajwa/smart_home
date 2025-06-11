from flask import Flask, jsonify
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

app = Flask(__name__)

# MongoDB connection details
uri = "mongodb+srv://alfarrelmahardika:Z.iLkvVg7Ep6!uP@cluster0.lnbl9.mongodb.net/"
db_name = "manajemen_listrik"
collection_name = "kipas_dan_lampu"

# Initialize MongoDB client
try:
    mongo_client = MongoClient(uri)
    db = mongo_client[db_name]
    collection = db[collection_name]
    # Test the connection
    mongo_client.admin.command('ping')
    print("Successfully connected to MongoDB")
except ConnectionFailure as e:
    print(f"Failed to connect to MongoDB: {e}")
    exit(1)

@app.route('/latest-data', methods=['GET'])
def get_latest_data():
    try:
        # Fetch the latest document based on the timestamp field
        latest_data = collection.find_one(sort=[("timestamp", -1)])
        if latest_data:
            # Print the data to the terminal
            print("Latest data fetched:", latest_data)
            
            # Remove MongoDB's internal '_id' field from the response
            latest_data.pop('_id', None)
            return jsonify(latest_data), 200
        else:
            print("No data found")
            return jsonify({"message": "No data found"}), 404
    except Exception as e:
        print("Error fetching data:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)