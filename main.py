from flask import Flask, request, jsonify
from flasgger import Swagger
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Histogram, Counter, Gauge
import json
import os
import time

app = Flask(__name__)  
swagger = Swagger(app)
metrics = PrometheusMetrics(app)

# Path para o ficheiro de dados (vai estar na pasta NFS)
DATA_FILE = os.getenv('FILES_STORAGE_PATH', '/data/files.json')

# ===== MÉTRICAS CUSTOMIZADAS =====
# Tempo de operações no NFS
nfs_operation_time = Histogram(
    'nfs_file_operation_seconds', 
    'Time spent on NFS file operations',
    ['operation']  # labels: read, write
)

# Contador de ficheiros guardados
files_uploaded_total = Counter(
    'files_uploaded_total',
    'Total number of files uploaded'
)

# Tamanho atual do array de ficheiros
files_array_size = Gauge(
    'files_array_size',
    'Current number of files in storage'
)

# Tamanho do ficheiro JSON em bytes
json_file_size_bytes = Gauge(
    'json_file_size_bytes',
    'Size of the JSON file in bytes'
)

def load_files():
    """Carrega os ficheiros do JSON"""
    start = time.time()
    try:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
                    # Atualiza métrica de tamanho do array
                    files_array_size.set(len(data))
                    # Atualiza métrica de tamanho do ficheiro
                    json_file_size_bytes.set(os.path.getsize(DATA_FILE))
                    return data
            except:
                return []
        return []
    finally:
        # Regista tempo de leitura
        nfs_operation_time.labels(operation='read').observe(time.time() - start)

def save_files(files):
    """Guarda os ficheiros no JSON"""
    start = time.time()
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(files, f, indent=2)
        
        # Atualiza métricas após gravação
        files_array_size.set(len(files))
        if os.path.exists(DATA_FILE):
            json_file_size_bytes.set(os.path.getsize(DATA_FILE))
    finally:
        # Regista tempo de escrita
        nfs_operation_time.labels(operation='write').observe(time.time() - start)

@app.route('/files', methods=['GET'])
def get_files():
    """
    Get all files
    ---
    responses:
      200:
        description: Lista de arquivos
        schema:
          type: array
          items:
            type: string
    """
    files = load_files()
    return jsonify(files)

@app.route('/files', methods=['POST'])
def upload_file():
    """
    Upload a file
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            filename:
              type: string
    responses:
      201:
        description: Arquivo enviado
    """
    data = request.get_json()
    if not data or 'filename' not in data:
        return jsonify({'error': 'filename is required'}), 400
    
    file_name = data['filename']
    files = load_files()
    files.append(file_name)
    save_files(files)
    
    # Incrementa contador de uploads
    files_uploaded_total.inc()
    
    return jsonify({'message': 'File uploaded', 'file': file_name}), 201

@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint
    ---
    responses:
      200:
        description: Service is healthy
    """
    return jsonify({'status': 'healthy'}), 200


@app.route('/files', methods=['DELETE'])
def delete_file():
        """
        Delete a file by filename
        ---
        parameters:
            - name: body
                in: body
                required: false
                schema:
                    type: object
                    properties:
                        filename:
                            type: string
            - name: filename
                in: query
                required: false
                type: string
        responses:
            200:
                description: File deleted
            400:
                description: filename required
            404:
                description: file not found
        """
        data = request.get_json(silent=True) or {}
        filename = data.get('filename') or request.args.get('filename')
        if not filename:
                return jsonify({'error': 'filename is required'}), 400

        files = load_files()
        if filename not in files:
                return jsonify({'error': 'file not found'}), 404

        files = [f for f in files if f != filename]
        save_files(files)

        return jsonify({'message': 'File deleted', 'file': filename}), 200


@app.route('/files', methods=['PUT', 'PATCH'])
def update_file():
        """
        Update (rename) a file
        ---
        parameters:
            - name: body
                in: body
                required: true
                schema:
                    type: object
                    properties:
                        filename:
                            type: string
                        old_filename:
                            type: string
                        new_filename:
                            type: string
        responses:
            200:
                description: File updated
            400:
                description: bad request
            404:
                description: file not found
        """
        data = request.get_json(silent=True) or {}
        # accept either 'filename' or 'old_filename' for backward compatibility
        old = data.get('old_filename') or data.get('filename')
        new = data.get('new_filename')
        if not old or not new:
                return jsonify({'error': 'old_filename and new_filename are required'}), 400

        files = load_files()
        if old not in files:
                return jsonify({'error': 'file not found'}), 404
        if new in files:
                return jsonify({'error': 'new filename already exists'}), 400

        files = [new if f == old else f for f in files]
        save_files(files)

        return jsonify({'message': 'File updated', 'old': old, 'new': new}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)