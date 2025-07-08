import json
import time
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson import ObjectId
from bson.json_util import dumps, loads
from datetime import datetime
from flask_cors import CORS  # Import CORS

# Create the Flask application
app = Flask(__name__)

# Enable CORS for requests from localhost:8080
CORS(app, origins=["http://54.166.118.216:9090"])

# MongoDB connection URLs
uri_catalog = "mongodb://admin:admin123@35.175.23.86:27017/CatalogServiceDB?authSource=admin"
uri_backup = "mongodb://admin:admin123@35.175.23.86:27017/BackupServiceDB?authSource=admin"

# Connect to the databases
client_catalog = MongoClient(uri_catalog)
client_backup = MongoClient(uri_backup)

# Select the databases and collections
db_catalog = client_catalog['CatalogServiceDB']
db_backup = client_backup['BackupServiceDB']
fs_files_collection = db_catalog['fs.files']
fs_chunks_collection = db_catalog['fs.chunks']
images_collection = db_catalog['images']
backup_collection = db_backup['images']  # We will store image backups in this collection

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

# Function to restore images while keeping the same _id
@app.route('/restore_images', methods=['POST'])
def restore_images():
    restore_date = request.json.get('restore_date')
    backup_data = backup_collection.find_one({"backup_date": restore_date})

    if backup_data:
        images_to_restore = backup_data['images']

        for image_data in images_to_restore:
            # Restore only the correct fields in fs.files
            file_metadata = {
                "_id": ObjectId(image_data["_id"]),
                "filename": image_data["filename"],
                "chunkSize": image_data["chunkSize"],
                "length": image_data["length"],
                "uploadDate": image_data["uploadDate"]
            }
            fs_files_collection.replace_one({'_id': file_metadata['_id']}, file_metadata, upsert=True)

            # Restore the chunks in fs.chunks with the same _id and files_id
            for chunk in image_data["chunks"]:
                chunk_data = {
                    "_id": ObjectId(chunk["_id"]),
                    "files_id": ObjectId(chunk["files_id"]),
                    "n": chunk["n"],
                    "data": chunk["data"]
                }
                fs_chunks_collection.replace_one({'_id': chunk_data['_id']}, chunk_data, upsert=True)

            # Restore the relationship in images
            if "image_relation" in image_data:
                image_relation = image_data["image_relation"]
                images_collection.replace_one(
                    {"_id": ObjectId(image_relation["_id"])}, 
                    {
                        "_id": ObjectId(image_relation["_id"]),
                        "image_id": image_relation["image_id"],
                        "model_id": image_relation["model_id"],
                        "name": image_relation["name"]
                    },
                    upsert=True
                )

        # Save the restoration date
        restoration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        backup_collection.update_one(
            {"backup_date": restore_date},
            {"$set": {"restoration_date": restoration_date}}
        )

        return jsonify({"message": f"Images successfully restored with restoration date {restoration_date}"}), 201
    else:
        return jsonify({"message": "No backup found with the selected date"}), 404
    
# Function to get all available backups by creation date
@app.route('/backups', methods=['GET'])
def get_backups():
    # Get all backups ordered by date
    backups = backup_collection.find().sort("backup_date", -1)

    formatted_backups = []
    for backup in backups:
        formatted_backups.append({
            "backup_date": backup["backup_date"],
            "backup_id": str(backup["_id"])
        })

    return jsonify(formatted_backups)

# Health check route
@app.route('/images-rollback/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    # Run the service on port 6007
    app.run(debug=True, host='0.0.0.0', port=6007)