import json
import time
import psycopg2
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.json_util import dumps, loads
from datetime import datetime
from psycopg2.extras import RealDictCursor
from flask_cors import CORS  # Import CORS

# Create the Flask application
app = Flask(__name__)

# Enable CORS for requests from localhost:8080
CORS(app, origins=["http://54.166.118.216:9090"])

# PostgreSQL connection URL (Supabase)
POSTGRES_URI = "postgresql://admin:admin123@23.23.135.253:5432/mydb"

# MongoDB connection URL (Backup)
MONGO_URI = "mongodb://admin:admin123@35.175.23.86:27017/BackupServiceDB?authSource=admin"

# Connect to PostgreSQL
def connect_postgres():
    return psycopg2.connect(POSTGRES_URI, cursor_factory=RealDictCursor)

# Connect to MongoDB
client_mongo = MongoClient(MONGO_URI)
db_mongo = client_mongo['BackupServiceDB']
backup_collection = db_mongo['user']  # Backup collection

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

# Function to restore users from MongoDB to PostgreSQL
@app.route('/restore_users', methods=['POST'])
def restore_users():
    restore_date = request.json.get('restore_date')

    # Search for the backup in MongoDB
    backup_data = backup_collection.find_one({"backup_date": restore_date})

    if not backup_data:
        return jsonify({"message": "No backup found with the selected date"}), 404

    users_to_restore = backup_data['users']

    try:
        conn = connect_postgres()
        cursor = conn.cursor()

        # Restore the data by overwriting the table
        cursor.execute("DELETE FROM \"user\";")  # Change 'user' to the specific table name

        for user in users_to_restore:
            cursor.execute(
                """
                INSERT INTO "user" (id, username, password, first_name, last_name, dni, email, city)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE 
                SET username=EXCLUDED.username, password=EXCLUDED.password, 
                    first_name=EXCLUDED.first_name, last_name=EXCLUDED.last_name, 
                    dni=EXCLUDED.dni, email=EXCLUDED.email, city=EXCLUDED.city;
                """,
                (user['id'], user['username'], user['password'], user['first_name'],
                 user['last_name'], user['dni'], user['email'], user['city'])
            )

        conn.commit()
        cursor.close()
        conn.close()

        # Add the restoration date to the MongoDB document
        restoration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        backup_collection.update_one(
            {"backup_date": restore_date},
            {"$set": {"restoration_date": restoration_date}}
        )

        return jsonify({"message": f"Users successfully restored with restoration date {restoration_date}"}), 201

    except Exception as e:
        return jsonify({"message": f"Error restoring users: {str(e)}"}), 500
    
# Route to get all user backups by creation date
@app.route('/user_backups', methods=['GET'])
def get_user_backups():
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
@app.route('/rollback-user/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6010)