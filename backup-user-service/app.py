import json
import psycopg2
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.json_util import dumps, loads
from datetime import datetime
from psycopg2.extras import RealDictCursor
from flask_cors import CORS

# Crear la aplicación Flask
app = Flask(__name__)

# Habilitar CORS para solicitudes de localhost:8080
CORS(app, origins=["http://54.166.118.216:9090"])

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
backup_collection = db_mongo['user']  # Colección de respaldo

# Función para respaldar los usuarios de PostgreSQL en MongoDB
@app.route('/backup_users', methods=['POST'])
def backup_users():
    try:
        conn = connect_postgres()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM \"user\";")  # Cambiar 'users' por 'user'
        users = cursor.fetchall()
        cursor.close()
        conn.close()

        if not users:
            return jsonify({"message": "No se encontraron usuarios para respaldar"}), 400

        # Agregar fecha de respaldo y convertir UUID a string
        backup_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for user in users:
            user['id'] = str(user['id'])  # Convertimos UUID a string

        backup_data = {
            'backup_date': backup_date,
            'users': users
        }

        backup_collection.insert_one(backup_data)

        return jsonify({"message": f"Usuarios respaldados exitosamente con fecha {backup_date}"}), 201

    except Exception as e:
        return jsonify({"message": f"Error al respaldar usuarios: {str(e)}"}), 500
    
# Ruta para obtener el tiempo transcurrido desde el último respaldo de usuario
@app.route('/last_user_backup', methods=['GET'])
def get_last_user_backup_time():
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
    app.run(debug=True, host='0.0.0.0', port=6005)