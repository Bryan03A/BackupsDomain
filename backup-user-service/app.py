import json
import psycopg2
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.json_util import dumps, loads
from datetime import datetime
from psycopg2.extras import RealDictCursor
from flask_cors import CORS

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

# Function to back up users from PostgreSQL to MongoDB
@app.route('/backup_users', methods=['POST'])
def backup_users():
    try:
        conn = connect_postgres()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM \"user\";")  # Change 'user' to the appropriate table name
        users = cursor.fetchall()
        cursor.close()
        conn.close()

        if not users:
            return jsonify({"message": "No users found to back up"}), 400

        # Add backup date and convert UUID to string
        backup_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for user in users:
            user['id'] = str(user['id'])  # Convert UUID to string

        backup_data = {
            'backup_date': backup_date,
            'users': users
        }

        backup_collection.insert_one(backup_data)

        return jsonify({"message": f"Users successfully backed up with date {backup_date}"}), 201

    except Exception as e:
        return jsonify({"message": f"Error backing up users: {str(e)}"}), 500
    
# Route to get the time elapsed since the last user backup
@app.route('/last_user_backup', methods=['GET'])
def get_last_user_backup_time():
    # Get the last recorded backup from the backup collection
    last_backup = backup_collection.find_one(sort=[("backup_date", -1)])  # Make sure the field is "backup_date"

    if last_backup:
        last_backup_timestamp = last_backup['backup_date']
        last_backup_datetime = datetime.strptime(last_backup_timestamp, "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - last_backup_datetime
        
        # Convert the time difference to days, hours, minutes, and seconds
        seconds = time_diff.total_seconds()
        days = int(seconds // (24 * 3600))
        hours = int((seconds % (24 * 3600)) // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        time_elapsed = f"{days}d {hours}h {minutes}m {seconds}s"
        
        return jsonify({
            "last_backup_timestamp": last_backup_timestamp,
            "time_elapsed": time_elapsed
        })
    else:
        return jsonify({"message": "No backups available"}), 404
    
# Health check route
@app.route('backup-user/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6005)