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
backup_collection = db_mongo['orders']  # Backup collection

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

# Function to restore orders from MongoDB to PostgreSQL
@app.route('/restore_orders', methods=['POST'])
def restore_orders():
    restore_date = request.json.get('restore_date')

    # Search for the backup in MongoDB
    backup_data = backup_collection.find_one({"backup_date": restore_date})

    if not backup_data:
        return jsonify({"message": "No backup found with the selected date"}), 404

    orders_to_restore = backup_data['orders']

    try:
        conn = connect_postgres()
        cursor = conn.cursor()

        # Restore the data by overwriting the table
        cursor.execute("DELETE FROM \"orders\";")  # Change 'orders' to your specific table name

        for order in orders_to_restore:
            cursor.execute(
                """
                INSERT INTO "orders" (id, order_id, requester_id, requested, accepted, completed, paid, alert, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE 
                SET order_id=EXCLUDED.order_id, requester_id=EXCLUDED.requester_id, 
                    requested=EXCLUDED.requested, accepted=EXCLUDED.accepted, 
                    completed=EXCLUDED.completed, paid=EXCLUDED.paid, alert=EXCLUDED.alert,
                    created_by=EXCLUDED.created_by;
                """,
                (order['id'], order['order_id'], order['requester_id'], order['requested'],
                 order['accepted'], order['completed'], order['paid'], order['alert'], order['created_by'])
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

        return jsonify({"message": f"Orders successfully restored with restoration date {restoration_date}"}), 201

    except Exception as e:
        return jsonify({"message": f"Error restoring orders: {str(e)}"}), 500
    
# Route to get all backups by creation date
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
@app.route('/rollback-orders/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6009)