# Mock Storage API server (Flask) - simple in-memory store
from flask import Flask, jsonify, request, abort
import uuid, time
import random

app = Flask(__name__)
VOLUMES = []
BACKUPS = []

# --- Volume Management Endpoints (/api/v1/volumes) ---
@app.route('/api/v1/volumes', methods=['GET','POST'])
def volumes():
    if request.method == 'POST':
        data = request.get_json()
        
        # Validate required fields for creation
        if not data or 'name' not in data or 'size_gb' not in data:
            abort(400, description="Missing required fields: 'name' and 'size_gb'")
            
        vol = {
            'id': str(uuid.uuid4()),
            'name': data.get('name'),
            'size_gb': data.get('size_gb'),
            'status': 'available', # Default status for a new volume
            'created': time.time()
        }
        VOLUMES.append(vol)
        return jsonify(vol), 201 # 201 Created
    else:
        # GET: Return the list of all volumes
        return jsonify({'volumes': VOLUMES}), 200 # 200 OK

@app.route('/api/v1/volumes/<vid>', methods=['DELETE'])
def delete_volume(vid):
    global VOLUMES
    # Filter out the volume with the specified ID
    VOLUMES = [v for v in VOLUMES if v['id'] != vid]
    return jsonify({'deleted': vid}), 200

# --- Backup Trigger Endpoint (/api/v1/backup) ---
# @app.route('/api/v1/backup', methods=['POST'])
@app.route('/api/v1/volumes/trigger-backup', methods=['POST'])
def backup():
    data = request.get_json()
    vol_name = data.get('volume')
    
    # Validation 1: Check for required 'volume' field
    if not vol_name:
        abort(400, description="Missing required field: 'volume'")
    
    # Validation 2: Check if the volume actually exists in the VOLUMES list
    volume_exists = any(v['name'] == vol_name for v in VOLUMES)
    
    if not volume_exists:
        # If volume not found, return 404 Not Found (CRITICAL FIX)
        abort(404, description=f"Volume '{vol_name}' not found.")

    # Simulate backup success/failure pseudo-randomly
    success = random.choice([True, True, True, False])  # 75% chance to succeed
    backup_entry = {
        'id': str(uuid.uuid4()), 
        'volume': vol_name, 
        'status': 'passed' if success else 'failed', 
        'ts': time.time()
    }
    BACKUPS.append(backup_entry)
    
    return jsonify(backup_entry), 200

if __name__ == '__main__':
    # Flask application entry point
    app.run(host='0.0.0.0', port=5000)    