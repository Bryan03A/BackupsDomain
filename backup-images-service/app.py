import json
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson import ObjectId
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

# Límite de solicitudes por minuto
MAX_REQUESTS_PER_MINUTE = 100

# Función para eliminar el campo _id de los documentos
def format_images(images):
    formatted_images = []
    for image in images:
        image['_id'] = str(image['_id'])  # Convertir ObjectId a string
        formatted_images.append(image)
    return formatted_images

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

# Función para respaldar las imágenes
@app.route('/backup_images', methods=['POST'])
def backup_images():
    images_info = fs_files_collection.find()

    images_to_backup = []
    for image in images_info:
        image_copy = {
            "_id": str(image["_id"]),  # Guardamos el ObjectId original como string
            "filename": image["filename"],
            "chunkSize": image["chunkSize"],
            "length": image["length"],
            "uploadDate": image["uploadDate"],
            "chunks": []  # Lista para almacenar los chunks binarios de esta imagen
        }

        # Obtener los chunks de la imagen
        chunks = fs_chunks_collection.find({"files_id": image["_id"]})
        for chunk in chunks:
            chunk_copy = {
                "_id": str(chunk["_id"]),  # Guardar el ObjectId del chunk
                "files_id": str(chunk["files_id"]),  # Guardar el ObjectId del archivo
                "n": chunk["n"],
                "data": chunk["data"]
            }
            image_copy["chunks"].append(chunk_copy)

        # Respaldar la relación en la colección images
        image_relation = images_collection.find_one({"image_id": str(image["_id"])})
        if image_relation:
            image_copy["image_relation"] = {
                "_id": str(image_relation["_id"]),
                "name": image_relation["name"],  
                "image_id": str(image_relation["image_id"]),
                "model_id": str(image_relation["model_id"])
            }

        images_to_backup.append(image_copy)

    if images_to_backup:
        backup_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        backup_data = {
            'backup_date': backup_date,
            'images': images_to_backup
        }

        backup_collection.insert_one(backup_data)

        return jsonify({"message": f"Imágenes respaldadas exitosamente con fecha {backup_date} en 'BackupServiceDB'"}), 201
    else:
        return jsonify({"message": "No se encontraron imágenes para respaldar"}), 400
    
@app.route('/last_backup', methods=['GET'])
def last_backup():
    # Obtener el último backup realizado, ordenado por fecha descendente
    last_backup = backup_collection.find_one(sort=[("backup_date", -1)])  # Verifica que el campo es "backup_date"
    
    if last_backup:
        last_backup_time = datetime.strptime(last_backup['backup_date'], '%Y-%m-%d %H:%M:%S')
        current_time = datetime.now()
        time_diff = current_time - last_backup_time
        seconds = time_diff.total_seconds()
        days = int(seconds // (24 * 3600))
        hours = int((seconds % (24 * 3600)) // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        time_elapsed = f"{days}d {hours}h {minutes}m {seconds}s"
        
        return jsonify({
            "last_backup_timestamp": last_backup['backup_date'],
            "time_elapsed": time_elapsed
        })
    else:
        return jsonify({"message": "No hay backups disponibles"}), 404
    
# Ruta para la comprobación de salud
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6002)