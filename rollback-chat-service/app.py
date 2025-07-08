import json
import time
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.json_util import dumps, loads
from datetime import datetime
from flask_cors import CORS  # Importa CORS

# Crear la aplicación Flask
app = Flask(__name__)

# Habilitar CORS para solicitudes de localhost:8080
CORS(app, origins=["http://54.173.251.44:9090"])

# URL de conexión a MongoDB (Base de datos principal y Backup)
uri = "mongodb+srv://MicroserviceDev:1997999@cluster0.hdqpd.mongodb.net/ChatServiceDB?retryWrites=true&w=majority"
uri_backup = "mongodb+srv://MicroserviceDev:1997999@cluster0.hdqpd.mongodb.net/BackupServiceDB?retryWrites=true&w=majority"

# Conectar a la base de datos principal
client = MongoClient(uri)
db = client['ChatServiceDB']
original_collection = db['chats']

# Conectar a la base de datos de respaldo
client_backup = MongoClient(uri_backup)
backup_db = client_backup['BackupServiceDB']
backup_collection = backup_db['chat']  # Renombrado a 'chat'

# Función para eliminar el campo _id de los documentos
def format_chats(chats):
    formatted_chats = []
    for chat in chats:
        chat['_id'] = str(chat['_id'])  # Convertir ObjectId a string
        formatted_chats.append(chat)
    return formatted_chats

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

@app.route('/restore_chats', methods=['POST'])
def restore_chats():
    # Obtener la fecha del respaldo a restaurar desde los parámetros de la solicitud
    try:
        # Obtener la fecha proporcionada por el usuario
        restore_date = request.json.get('restore_date')  # formato: 'YYYY-MM-DD HH:MM:SS'
        
        # Buscar el backup con la fecha especificada
        last_backup = backup_collection.find({"backup_timestamp": restore_date}).limit(1)
        
        if last_backup:
            backup_data = last_backup[0]
            chats_data = backup_data['chats']
            
            # Insertar los datos restaurados en la colección original 'chats' (sobrescribir)
            restoration_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            backup_collection.update_one(
                {"_id": backup_data["_id"]},
                {"$set": {"restoration_timestamp": restoration_timestamp}}  # Guardamos la fecha de restauración
            )
            
            # Sobrescribir los datos en la colección original
            original_collection.drop()  # Eliminar los chats actuales (sobrescribirlos)
            original_collection.insert_many(chats_data)  # Restaurar los chats desde el backup
            
            return jsonify({
                "message": f"Datos restaurados exitosamente en 'chats' con fecha de restauración {restoration_timestamp}"
            }), 201
        else:
            return jsonify({"message": "No se encontraron respaldos con la fecha especificada"}), 404
    except Exception as e:
        return jsonify({"message": f"Error al restaurar los datos: {str(e)}"}), 500

# Ruta para obtener todos los backups disponibles
@app.route('/backups', methods=['GET'])
def get_backups():
    backups = backup_collection.find({}, {"backup_timestamp": 1, "_id": 0}).sort("backup_timestamp", -1)
    backup_dates = [backup['backup_timestamp'] for backup in backups]
    
    if backup_dates:
        return jsonify({"backups": backup_dates})
    else:
        return jsonify({"message": "No hay backups disponibles"}), 404
    
# Ruta para la comprobación de salud
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    # Ejecutar el servicio en el puerto 6006
    app.run(debug=True, host='0.0.0.0', port=6006)