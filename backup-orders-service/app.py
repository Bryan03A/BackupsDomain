import json
import psycopg2
from flask import Flask, jsonify, request
from pymongo import MongoClient
from datetime import datetime
import time
from psycopg2.extras import RealDictCursor
from flask_cors import CORS  # Importa CORS

# Crear la aplicación Flask
app = Flask(__name__)

# Habilitar CORS para solicitudes de localhost:8080
CORS(app, origins=["http://54.173.251.44:9090"])

# URL de conexión a PostgreSQL (Supabase)
POSTGRES_URI = "postgresql://admin:admin123@23.23.135.253:5432/mydb"

# URL de conexión a MongoDB (Backup)
MONGO_URI = "mongodb://admin:admin123@35.175.23.86:27017/BackupServiceDB?authSource=admin"

# Conectar a PostgreSQL
def connect_postgres():
    return psycopg2.connect(POSTGRES_URI, cursor_factory=RealDictCursor)

# Conectar a MongoDB
client_mongo = MongoClient(MONGO_URI)
db_mongo = client_mongo['BackupServiceDB']
backup_collection = db_mongo['orders']  # Colección de respaldo

# Diccionario para almacenar la cantidad de solicitudes por IP
requests_per_ip = {}

# Límite de solicitudes por minuto
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

# Función para respaldar los pedidos de PostgreSQL en MongoDB
@app.route('/backup_orders', methods=['POST'])
def backup_orders():
    try:
        conn = connect_postgres()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM \"orders\";")  # Cambiar 'orders' por 'orders'
        orders = cursor.fetchall()
        cursor.close()
        conn.close()

        if not orders:
            return jsonify({"message": "No se encontraron pedidos para respaldar"}), 400

        # Agregar fecha de respaldo
        backup_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for order in orders:
            order['id'] = str(order['id'])  # Convertimos UUID a string

        backup_data = {
            'backup_date': backup_date,
            'orders': orders
        }

        backup_collection.insert_one(backup_data)

        return jsonify({"message": f"Pedidos respaldados exitosamente con fecha {backup_date}"}), 201

    except Exception as e:
        return jsonify({"message": f"Error al respaldar pedidos: {str(e)}"}), 500
    
# Ruta para obtener el tiempo transcurrido desde el último respaldo
@app.route('/last_backup', methods=['GET'])
def get_last_backup_time():
    # Obtener el último backup registrado en la colección de respaldos
    last_backup = backup_collection.find_one(sort=[("backup_date", -1)])  # Verifica que el campo es "backup_date"

    if last_backup:
        last_backup_timestamp = last_backup['backup_date']
        last_backup_datetime = datetime.strptime(last_backup_timestamp, "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - last_backup_datetime
        
        # Convertir la diferencia de tiempo a días, horas, minutos y segundos
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
        return jsonify({"message": "No hay backups disponibles"}), 404
    
# Ruta para la comprobación de salud
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6004)