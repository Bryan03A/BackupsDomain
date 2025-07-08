import json
from flask import Flask, jsonify, request
from pymongo import MongoClient
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

# Request limit per minute
MAX_REQUESTS_PER_MINUTE = 100

# Function to remove the _id field from documents (if necessary)
def format_models(models):
    formatted_models = []
    for model in models:
        formatted_models.append(model)
    return formatted_models

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

# Route to get models
@app.route('/models', methods=['GET'])
def get_models():
    # Get all the documents from the models collection
    models = models_collection.find()
    
    # Format the models and return as a response
    formatted_models = format_models(models)
    return jsonify(formatted_models)

# Route to back up models
@app.route('/backup_models', methods=['POST'])
def backup_models():
    # Get all the documents from the models collection
    models = models_collection.find()

    # Create a list of models to copy
    models_to_backup = []
    for model in models:
        # Keep the _id field to restore with the same value
        model_copy = model.copy()
        models_to_backup.append(model_copy)

    # Insert the documents into the 'models' collection in BackupServiceDB
    if models_to_backup:
        # Get the current date to use as the backup identifier
        backup_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        backup_data = {
            'backup_date': backup_date,
            'models': models_to_backup
        }

        backup_collection.insert_one(backup_data)
        
        return jsonify({"message": f"Models successfully backed up with date {backup_date} in 'BackupServiceDB'"}), 201
    else:
        return jsonify({"message": "No models found to back up"}), 400
    
# Route to get the time elapsed since the last backup
@app.route('/last_backup', methods=['GET'])
def get_last_backup_time():
    last_backup = backup_collection.find().sort("backup_date", -1).limit(1)  # Get the last backup
    last_backup = list(last_backup)  # Convert the cursor to a list

    if last_backup:  # If the list is not empty
        last_backup_timestamp = last_backup[0]['backup_date']
        last_backup_datetime = datetime.strptime(last_backup_timestamp, "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - last_backup_datetime
        return jsonify({
            "last_backup_timestamp": last_backup_timestamp,
            "time_since_last_backup": str(time_diff)
        })
    else:
        return jsonify({"message": "No backups found"}), 404
    
# Health check route
@app.route('/backup-models/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    # Run the service on port 5001
    app.run(debug=True, host='0.0.0.0', port=6003)