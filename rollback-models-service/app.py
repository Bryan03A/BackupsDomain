import json
import time
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.json_util import dumps, loads
from datetime import datetime
from flask_cors import CORS  # Import CORS

# Create the Flask application
app = Flask(__name__)

# Enable CORS for requests from localhost:9090
CORS(app, origins=["http://54.166.118.216:9090"])

# MongoDB connection URLs
uri_catalog = "mongodb://admin:admin123@35.175.23.86:27017/CatalogServiceDB?authSource=admin"
uri_backup = "mongodb://admin:admin123@35.175.23.86:27017/BackupServiceDB?authSource=admin"

# Connect to the database
client_catalog = MongoClient(uri_catalog)
client_backup = MongoClient(uri_backup)

# Select the database and collections
db_catalog = client_catalog['CatalogServiceDB']
db_backup = client_backup['BackupServiceDB']
models_collection = db_catalog['models']
backup_collection = db_backup['models']  # We will store the backups in this collection

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

# Function to remove the _id field from documents (if necessary)
def format_models(models):
    formatted_models = []
    for model in models:
        # Remove the _id field only if necessary, otherwise keep it
        formatted_models.append(model)
    return formatted_models

@app.route('/catalog', methods=['GET'])
def get_models():
    # Get all documents from the models collection
    models = models_collection.find()
    
    # Format the models and return as a response
    formatted_models = format_models(models)
    return jsonify(formatted_models)

@app.route('/restore_catalog', methods=['POST'])
def restore_models():
    # Get the selected backup date to restore the models
    restore_date = request.json.get('restore_date')

    # Find the corresponding backup in the backup collection
    backup_data = backup_collection.find_one({"backup_date": restore_date})

    if backup_data:
        # Restore the models in the original collection
        models_to_restore = backup_data['models']

        # Delete the current models and restore the new ones (keeping the _id)
        models_collection.delete_many({})  # Delete all current models
        models_collection.insert_many(models_to_restore)  # Insert the restored models with the same _id

        # Save the restoration date
        restoration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Add the restoration date to the BackupServiceDB database
        backup_collection.update_one(
            {"backup_date": restore_date},
            {"$set": {"restoration_date": restoration_date}}
        )

        return jsonify({"message": f"Models successfully restored with restoration date {restoration_date}"}), 201
    else:
        return jsonify({"message": "No backup found with the selected date"}), 404
    
# Route to get all available backups by creation date
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
@app.route('/rollback-models/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    # Run the service on port 6008
    app.run(debug=True, host='0.0.0.0', port=6008)