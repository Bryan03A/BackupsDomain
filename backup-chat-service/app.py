import json
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.json_util import dumps, loads
from bson import ObjectId
from datetime import datetime
from flask_cors import CORS
import time

# Create the Flask application
app = Flask(__name__)

# Enable CORS for requests from localhost:8080
CORS(app, origins=["http://54.166.118.216:9090"])

# MongoDB connection URLs (Main database and Backup)
uri = "mongodb://admin:admin123@35.175.23.86:27017/ChatServiceDB"
uri_backup = "mongodb://admin:admin123@35.175.23.86:27017/BackupServiceDB"

# Connect to the main database
client = MongoClient(uri)
db = client['ChatServiceDB']
original_collection = db['chats']

# Connect to the backup database
client_backup = MongoClient(uri_backup)
backup_db = client_backup['BackupServiceDB']
backup_collection = backup_db['chat']  # Renamed to 'chat'

# Dictionary to store the number of requests per IP
requests_per_ip = {}

# Request limit per minute
MAX_REQUESTS_PER_MINUTE = 100

# Function to remove the _id field from documents
def format_chats(chats):
    formatted_chats = []
    for chat in chats:
        chat['_id'] = str(chat['_id'])  # Convert ObjectId to string
        formatted_chats.append(chat)
    return formatted_chats

# Rate limiting function to avoid request abuse
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

@app.route('/copy_chats', methods=['POST'])
def copy_chats():
    # Get all documents from the original collection
    chats = original_collection.find()

    # Create a list with the chats to copy (without the _id field)
    chats_to_copy = []
    for chat in chats:
        chat_copy = chat.copy()
        chat_copy.pop('_id', None)  # Remove the _id field, MongoDB generates a new one
        chats_to_copy.append(chat_copy)

    # Insert documents into the 'chat' collection in BackupServiceDB
    if chats_to_copy:
        # Save chats to the backup collection in BackupServiceDB
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        backup_data = {
            "backup_timestamp": timestamp,
            "chats": chats_to_copy
        }
        
        # Save chats in the 'chat' collection in BackupServiceDB
        backup_collection.insert_one(backup_data)
        
        return jsonify({"message": f"Collection backed up with timestamp {timestamp} in 'chat' of BackupServiceDB"}), 201
    else:
        return jsonify({"message": "No chats found to copy"}), 400

# Route to get the time elapsed since the last backup
@app.route('/last_backup', methods=['GET'])
def last_backup():
    # Get the last backup performed
    last_backup = backup_collection.find_one(sort=[("backup_timestamp", -1)])
    
    if last_backup:
        last_backup_time = datetime.strptime(last_backup['backup_timestamp'], '%Y-%m-%d %H:%M:%S')
        current_time = datetime.now()
        time_diff = current_time - last_backup_time
        seconds = time_diff.total_seconds()
        days = int(seconds // (24 * 3600))
        hours = int((seconds % (24 * 3600)) // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        time_elapsed = f"{days}d {hours}h {minutes}m {seconds}s"
        
        return jsonify({
            "last_backup_timestamp": last_backup['backup_timestamp'],
            "time_elapsed": time_elapsed
        })
    else:
        return jsonify({"message": "No backups available"}), 404
    
# Health check route
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    # Run the service on port 5000
    app.run(debug=True, host='0.0.0.0', port=6001)