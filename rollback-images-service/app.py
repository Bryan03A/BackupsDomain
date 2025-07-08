import json
import time
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson import ObjectId
from bson.json_util import dumps, loads
from datetime import datetime
from flask_cors import CORS  # Importa CORS

# Crear la aplicación Flask
app = Flask(__name__)

# Habilitar CORS para solicitudes de localhost:8080
CORS(app, origins=["http://54.173.251.44:9090"])

# URL de conexión a MongoDB
uri_catalog = "mongodb+srv://MicroserviceDev:1997999@cluster0.hdqpd.mongodb.net/CatalogServiceDB?retryWrites=true&w=majority"
uri_backup = "mongodb+srv://MicroserviceDev:1997999@cluster0.hdqpd.mongodb.net/BackupServiceDB?retryWrites=true&w=majority"

# Conectar a las bases de datos
client_catalog = MongoClient(uri_catalog)
client_backup = MongoClient(uri_backup)

# Seleccionar las bases de datos y colecciones
db_catalog = client_catalog['CatalogServiceDB']
db_backup = client_backup['BackupServiceDB']
fs_files_collection = db_catalog['fs.files']
fs_chunks_collection = db_catalog['fs.chunks']
images_collection = db_catalog['images']
backup_collection = db_backup['images']  # Guardaremos los backups de imágenes en esta colección

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

# Función para restaurar las imágenes manteniendo el mismo _id
@app.route('/restore_images', methods=['POST'])
def restore_images():
    restore_date = request.json.get('restore_date')
    backup_data = backup_collection.find_one({"backup_date": restore_date})

    if backup_data:
        images_to_restore = backup_data['images']

        for image_data in images_to_restore:
            # Restaurar solo los campos correctos en fs.files
            file_metadata = {
                "_id": ObjectId(image_data["_id"]),
                "filename": image_data["filename"],
                "chunkSize": image_data["chunkSize"],
                "length": image_data["length"],
                "uploadDate": image_data["uploadDate"]
            }
            fs_files_collection.replace_one({'_id': file_metadata['_id']}, file_metadata, upsert=True)

            # Restaurar los chunks en fs.chunks con los mismos _id y files_id
            for chunk in image_data["chunks"]:
                chunk_data = {
                    "_id": ObjectId(chunk["_id"]),
                    "files_id": ObjectId(chunk["files_id"]),
                    "n": chunk["n"],
                    "data": chunk["data"]
                }
                fs_chunks_collection.replace_one({'_id': chunk_data['_id']}, chunk_data, upsert=True)

            # Restaurar la relación en images
            if "image_relation" in image_data:
                image_relation = image_data["image_relation"]
                images_collection.replace_one(
                    {"_id": ObjectId(image_relation["_id"])}, 
                    {
                        "_id": ObjectId(image_relation["_id"]),
                        "image_id": image_relation["image_id"],
                        "model_id": image_relation["model_id"],
                        "name": image_relation["name"]
                    },
                    upsert=True
                )

        # Guardar la fecha de restauración
        restoration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        backup_collection.update_one(
            {"backup_date": restore_date},
            {"$set": {"restoration_date": restoration_date}}
        )

        return jsonify({"message": f"Imágenes restauradas exitosamente con fecha de restauración {restoration_date}"}), 201
    else:
        return jsonify({"message": "No se encontró un respaldo con la fecha seleccionada"}), 404
    
# Función para obtener todos los backups disponibles por fecha de creación
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
    # Ejecutar el servicio en el puerto 6007
    app.run(debug=True, host='0.0.0.0', port=6007)