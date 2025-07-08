import json
import time
import psycopg2
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.json_util import dumps, loads
from datetime import datetime
from psycopg2.extras import RealDictCursor
from flask_cors import CORS  # Importar CORS

# Crear la aplicación Flask
app = Flask(__name__)

# Habilitar CORS para solicitudes desde localhost:8080
CORS(app, origins=["http://54.173.251.44:9090"])

# URL de conexión a PostgreSQL (Supabase)
POSTGRES_URI = "postgresql://postgres.imfqyzgimtercyyqeqof:1997Guallaba@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

# URL de conexión a MongoDB (Backup)
MONGO_URI = "mongodb+srv://MicroserviceDev:1997999@cluster0.hdqpd.mongodb.net/BackupServiceDB?retryWrites=true&w=majority"

# Conectar a PostgreSQL
def connect_postgres():
    return psycopg2.connect(POSTGRES_URI, cursor_factory=RealDictCursor)

# Conectar a MongoDB
client_mongo = MongoClient(MONGO_URI)
db_mongo = client_mongo['BackupServiceDB']
backup_collection = db_mongo['orders']  # Colección de respaldo

# Diccionario para almacenar la cantidad de solicitudes por IP
requests_per_ip = {}

# Límite de solicitudes por minuto (ejemplo: 100 solicitudes por minuto)
MAX_REQUESTS_PER_MINUTE = 100

# Función para implementar rate limiting (limitar las solicitudes)
@app.before_request
def limit_requests():
    ip = request.remote_addr
    current_time = int(time.time())  # Obtiene la hora actual en segundos
    if ip in requests_per_ip:
        requests_per_ip[ip] = [timestamp for timestamp in requests_per_ip[ip] if current_time - timestamp < 60]
    else:
        requests_per_ip[ip] = []
    
    # Si el número de solicitudes supera el límite, bloquea la solicitud
    if len(requests_per_ip[ip]) >= MAX_REQUESTS_PER_MINUTE:
        return jsonify({"message": "Too many requests. Please try again later."}), 429

    # Registra la nueva solicitud
    requests_per_ip[ip].append(current_time)

# Función para restaurar los pedidos desde MongoDB a PostgreSQL
@app.route('/restore_orders', methods=['POST'])
def restore_orders():
    restore_date = request.json.get('restore_date')

    # Buscar el respaldo en MongoDB
    backup_data = backup_collection.find_one({"backup_date": restore_date})

    if not backup_data:
        return jsonify({"message": "No se encontró un respaldo con la fecha seleccionada"}), 404

    orders_to_restore = backup_data['orders']

    try:
        conn = connect_postgres()
        cursor = conn.cursor()

        # Restaurar los datos sobrescribiendo la tabla
        cursor.execute("DELETE FROM \"orders\";")  # Cambiar 'orders' por 'orders'

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

        # Agregar la fecha de restauración al documento en MongoDB
        restoration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        backup_collection.update_one(
            {"backup_date": restore_date},
            {"$set": {"restoration_date": restoration_date}}
        )

        return jsonify({"message": f"Pedidos restaurados exitosamente con fecha de restauración {restoration_date}"}), 201

    except Exception as e:
        return jsonify({"message": f"Error al restaurar pedidos: {str(e)}"}), 500
    
# Ruta para obtener todos los respaldos por fecha de creación
@app.route('/backups', methods=['GET'])
def get_backups():
    # Obtener todos los respaldos ordenados por fecha
    backups = backup_collection.find().sort("backup_date", -1)

    formatted_backups = []
    for backup in backups:
        formatted_backups.append({
            "backup_date": backup["backup_date"],
            "backup_id": str(backup["_id"])
        })

    return jsonify(formatted_backups)

# Ruta para la comprobación de salud
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6009)