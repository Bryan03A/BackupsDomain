import json
import time
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.json_util import dumps, loads
from datetime import datetime
from flask_cors import CORS  # Import CORS

# Create the Flask application
app = Flask(__name__)

# Enable CORS for requests from localhost:8080
CORS(app, origins=["http://54.166.118.216:9090"])

# MongoDB connection URL (Main database and Backup)
uri = "mongodb://admin:admin123@35.175.23.86:27017/CatalogServiceDB?authSource=admin"
uri_backup = "mongodb://admin:admin123@35.175.23.86:27017/BackupServiceDB?authSource=admin"

# Connect to the main database
client = MongoClient(uri)
db = client['ChatServiceDB']
original_collection = db['chats']

# Connect to the backup database
client_backup = MongoClient(uri_backup)
backup_db = client_backup['BackupServiceDB']
backup_collection = backup_db['chat']  # Renamed to 'chat'

# Function to remove the _id field from documents
def format_chats(chats):
    formatted_chats = []
    for chat in chats:
        chat['_id'] = str(chat['_id'])  # Convert ObjectId to string
        formatted_chats.append(chat)
    return formatted_chats

# Dictionary to store the number of requests per IP
requests_per_ip = {}

# Request limit per minute (example: 100 requests per minute)
MAX_REQUESTS_PER_MINUTE = 100

# Function to implement rate limiting
@app.before_request
def limit_requests():
    ip = request.remote_addr
    current_time = int(time.time())  # Get the current time in seconds
    if ip in requests_per_ip:
        requests_per_ip[ip] = [timestamp for timestamp in requests_per_ip[ip] if current_time - timestamp < 60]
    else:
        requests_per_ip[ip] = []
    
    # If the number of requests exceeds the limit, block the request
    if len(requests_per_ip[ip]) >= MAX_REQUESTS_PER_MINUTE:
        return jsonify({"message": "Too many requests. Please try again later."}), 429

    # Register the new request
    requests_per_ip[ip].append(current_time)

@app.route('/restore_chats', methods=['POST'])
def restore_chats():
    # Get the restore date from the request parameters
    try:
        # Get the date provided by the user
        restore_date = request.json.get('restore_date')  # format: 'YYYY-MM-DD HH:MM:SS'
        
        # Find the backup with the specified date
        last_backup = backup_collection.find({"backup_timestamp": restore_date}).limit(1)
        
        if last_backup:
            backup_data = last_backup[0]
            chats_data = backup_data['chats']
            
            # Insert the restored data into the original 'chats' collection (overwrite)
            restoration_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            backup_collection.update_one(
                {"_id": backup_data["_id"]},
                {"$set": {"restoration_timestamp": restoration_timestamp}}  # Save the restoration date
            )
            
            # Overwrite the data in the original collection
            original_collection.drop()  # Remove current chats (overwrite them)
            original_collection.insert_many(chats_data)  # Restore chats from the backup
            
            return jsonify({
                "message": f"Data successfully restored in 'chats' with restoration date {restoration_timestamp}"
            }), 201
        else:
            return jsonify({"message": "No backups found with the specified date"}), 404
    except Exception as e:
        return jsonify({"message": f"Error restoring data: {str(e)}"}), 500

# Route to get all available backups
@app.route('/backups', methods=['GET'])
def get_backups():
    backups = backup_collection.find({}, {"backup_timestamp": 1, "_id": 0}).sort("backup_timestamp", -1)
    backup_dates = [backup['backup_timestamp'] for backup in backups]
    
    if backup_dates:
        return jsonify({"backups": backup_dates})
    else:
        return jsonify({"message": "No backups available"}), 404
    
# Health check route
@app.route('chat-rollback/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    # Run the service on port 6006
    app.run(debug=True, host='0.0.0.0', port=6006)