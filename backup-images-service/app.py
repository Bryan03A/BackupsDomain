import json
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson import ObjectId
from bson.json_util import dumps, loads
from datetime import datetime
from flask_cors import CORS
import time

# Create the Flask application
app = Flask(__name__)

# Enable CORS for requests from localhost:8080
CORS(app, origins=["http://54.166.118.216:9090"])

# MongoDB connection URL
uri_catalog = "mongodb://admin:admin123@35.175.23.86:27017/CatalogServiceDB?authSource=admin"
uri_backup = "mongodb://admin:admin123@35.175.23.86:27017/BackupServiceDB?authSource=admin"

# Connect to the databases
client_catalog = MongoClient(uri_catalog)
client_backup = MongoClient(uri_backup)

# Select databases and collections
db_catalog = client_catalog['CatalogServiceDB']
db_backup = client_backup['BackupServiceDB']
fs_files_collection = db_catalog['fs.files']
fs_chunks_collection = db_catalog['fs.chunks']
images_collection = db_catalog['images']
backup_collection = db_backup['images']  # We will store image backups in this collection

# Dictionary to store the number of requests per IP
requests_per_ip = {}

# Request limit per minute
MAX_REQUESTS_PER_MINUTE = 100

# Function to remove the _id field from documents
def format_images(images):
    formatted_images = []
    for image in images:
        image['_id'] = str(image['_id'])  # Convert ObjectId to string
        formatted_images.append(image)
    return formatted_images

# Rate limiting function to prevent request abuse
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

# Function to back up the images
@app.route('/backup_images', methods=['POST'])
def backup_images():
    images_info = fs_files_collection.find()

    images_to_backup = []
    for image in images_info:
        image_copy = {
            "_id": str(image["_id"]),  # Save the original ObjectId as a string
            "filename": image["filename"],
            "chunkSize": image["chunkSize"],
            "length": image["length"],
            "uploadDate": image["uploadDate"],
            "chunks": []  # List to store the binary chunks of this image
        }

        # Get the chunks for the image
        chunks = fs_chunks_collection.find({"files_id": image["_id"]})
        for chunk in chunks:
            chunk_copy = {
                "_id": str(chunk["_id"]),  # Save the chunk's ObjectId
                "files_id": str(chunk["files_id"]),  # Save the file's ObjectId
                "n": chunk["n"],
                "data": chunk["data"]
            }
            image_copy["chunks"].append(chunk_copy)

        # Back up the relationship in the images collection
        image_relation = images_collection.find_one({"image_id": str(image["_id"])})
        if image_relation:
            image_copy["image_relation"] = {
                "_id": str(image_relation["_id"]),
                "name": image_relation["name"],  
                "image_id": str(image_relation["image_id"]),
                "model_id": str(image_relation["model_id"])
            }

        images_to_backup.append(image_copy)

    if images_to_backup:
        backup_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        backup_data = {
            'backup_date': backup_date,
            'images': images_to_backup
        }

        backup_collection.insert_one(backup_data)

        return jsonify({"message": f"Images successfully backed up with date {backup_date} in 'BackupServiceDB'"}), 201
    else:
        return jsonify({"message": "No images found to back up"}), 400
    
@app.route('/last_backup', methods=['GET'])
def last_backup():
    # Get the last backup made, sorted by descending date
    last_backup = backup_collection.find_one(sort=[("backup_date", -1)])  # Ensure the field is "backup_date"
    
    if last_backup:
        last_backup_time = datetime.strptime(last_backup['backup_date'], '%Y-%m-%d %H:%M:%S')
        current_time = datetime.now()
        time_diff = current_time - last_backup_time
        seconds = time_diff.total_seconds()
        days = int(seconds // (24 * 3600))
        hours = int((seconds % (24 * 3600)) // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        time_elapsed = f"{days}d {hours}h {minutes}m {seconds}s"
        
        return jsonify({
            "last_backup_timestamp": last_backup['backup_date'],
            "time_elapsed": time_elapsed
        })
    else:
        return jsonify({"message": "No backups available"}), 404
    
# Health check route
@app.route('/backup-images/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6002)