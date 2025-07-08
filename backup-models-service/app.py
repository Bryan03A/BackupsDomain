import json
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.json_util import dumps, loads
from datetime import datetime
from flask_cors import CORS
import time

# Crear la aplicación Flask
app = Flask(__name__)

# Habilitar CORS para solicitudes de localhost:8080
CORS(app, origins=["http://54.173.251.44:9090"])

# URL de conexión a MongoDB
uri_catalog = "mongodb+srv://MicroserviceDev:1997999@cluster0.hdqpd.mongodb.net/CatalogServiceDB?retryWrites=true&w=majority"
uri_backup = "mongodb+srv://MicroserviceDev:1997999@cluster0.hdqpd.mongodb.net/BackupServiceDB?retryWrites=true&w=majority"

# Conectar a la base de datos
client_catalog = MongoClient(uri_catalog)
client_backup = MongoClient(uri_backup)

# Seleccionar la base de datos y las colecciones
db_catalog = client_catalog['CatalogServiceDB']
db_backup = client_backup['BackupServiceDB']
models_collection = db_catalog['models']
backup_collection = db_backup['models']  # Guardaremos los backups en esta colección

# Diccionario para almacenar la cantidad de solicitudes por IP
requests_per_ip = {}

# Límite de solicitudes por minuto
MAX_REQUESTS_PER_MINUTE = 100

# Función para eliminar el campo _id de los documentos (si es necesario)
def format_models(models):
    formatted_models = []
    for model in models:
        formatted_models.append(model)
    return formatted_models

# Función de rate limiting para evitar abuso de solicitudes
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

# Ruta para obtener modelos
@app.route('/models', methods=['GET'])
def get_models():
    # Obtener todos los documentos de la colección de modelos
    models = models_collection.find()
    
    # Formatear los modelos y devolver como respuesta
    formatted_models = format_models(models)
    return jsonify(formatted_models)

# Ruta para respaldar los modelos
@app.route('/backup_models', methods=['POST'])
def backup_models():
    # Obtener todos los documentos de la colección de modelos
    models = models_collection.find()

    # Crear una lista con los modelos a copiar
    models_to_backup = []
    for model in models:
        # Mantenemos el campo _id para que se restaure con el mismo valor
        model_copy = model.copy()
        models_to_backup.append(model_copy)

    # Insertar los documentos en la colección 'models' en BackupServiceDB
    if models_to_backup:
        # Obtener la fecha actual para usarla como identificador del backup
        backup_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        backup_data = {
            'backup_date': backup_date,
            'models': models_to_backup
        }

        backup_collection.insert_one(backup_data)
        
        return jsonify({"message": f"Modelos respaldados exitosamente con fecha {backup_date} en 'BackupServiceDB'"}), 201
    else:
        return jsonify({"message": "No se encontraron modelos para respaldar"}), 400
    
# Ruta para obtener el tiempo transcurrido desde el último respaldo
@app.route('/last_backup', methods=['GET'])
def get_last_backup_time():
    last_backup = backup_collection.find().sort("backup_date", -1).limit(1)  # Obtener el último backup
    last_backup = list(last_backup)  # Convertir el cursor en una lista

    if last_backup:  # Si la lista no está vacía
        last_backup_timestamp = last_backup[0]['backup_date']
        last_backup_datetime = datetime.strptime(last_backup_timestamp, "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - last_backup_datetime
        return jsonify({
            "last_backup_timestamp": last_backup_timestamp,
            "time_since_last_backup": str(time_diff)
        })
    else:
        return jsonify({"message": "No backups found"}), 404
    
# Ruta para la comprobación de salud
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    # Ejecutar el servicio en el puerto 5001
    app.run(debug=True, host='0.0.0.0', port=6003)