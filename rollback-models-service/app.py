import json
import time
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.json_util import dumps, loads
from datetime import datetime
from flask_cors import CORS  # Importar CORS

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

# Función para eliminar el campo _id de los documentos (si es necesario)
def format_models(models):
    formatted_models = []
    for model in models:
        # Eliminar el campo _id solo si es necesario, si no, lo mantenemos
        formatted_models.append(model)
    return formatted_models

@app.route('/models', methods=['GET'])
def get_models():
    # Obtener todos los documentos de la colección de modelos
    models = models_collection.find()
    
    # Formatear los modelos y devolver como respuesta
    formatted_models = format_models(models)
    return jsonify(formatted_models)

@app.route('/restore_models', methods=['POST'])
def restore_models():
    # Obtener la fecha de respaldo seleccionada para restaurar los modelos
    restore_date = request.json.get('restore_date')

    # Buscar el respaldo correspondiente en la colección de backups
    backup_data = backup_collection.find_one({"backup_date": restore_date})

    if backup_data:
        # Restaurar los modelos en la colección original
        models_to_restore = backup_data['models']

        # Eliminar los modelos actuales y restaurar los nuevos (manteniendo los _id)
        models_collection.delete_many({})  # Eliminar todos los modelos actuales
        models_collection.insert_many(models_to_restore)  # Insertar los modelos restaurados con el mismo _id

        # Guardar la fecha de restauración
        restoration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Agregar la fecha de restauración a la base de datos de BackupServiceDB
        backup_collection.update_one(
            {"backup_date": restore_date},
            {"$set": {"restoration_date": restoration_date}}
        )

        return jsonify({"message": f"Modelos restaurados exitosamente con fecha de restauración {restoration_date}"}), 201
    else:
        return jsonify({"message": "No se encontró un respaldo con la fecha seleccionada"}), 404
    
# Ruta para obtener todos los respaldos por fecha de creación
@app.route('/backups', methods=['GET'])
def get_backups():
    # Obtener todos los backups ordenados por fecha
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
    # Ejecutar el servicio en el puerto 6008
    app.run(debug=True, host='0.0.0.0', port=6008)