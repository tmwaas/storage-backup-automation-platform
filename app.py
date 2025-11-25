from flask import Flask, jsonify, request
import boto3
import json
import uuid
import os
from datetime import datetime

app = Flask(__name__)

# -----------------------------
# MinIO / S3 Client Configuration
# -----------------------------
s3 = boto3.client(
    "s3",
    endpoint_url="http://minio:9000",
    aws_access_key_id="minio",
    aws_secret_access_key="minio123",
    region_name="us-east-1",
)

VOLUME_BUCKET = "storage-volumes"
BACKUP_BUCKET = "storage-volumes-backup"

# Ensure buckets exist at startup
def ensure_bucket(name):
    try:
        s3.head_bucket(Bucket=name)
    except Exception:
        s3.create_bucket(Bucket=name)

ensure_bucket(VOLUME_BUCKET)
ensure_bucket(BACKUP_BUCKET)

# -----------------------------
# Helper Functions
# -----------------------------
def list_volumes():
    """Return all volume metadata stored in MinIO."""
    objects = s3.list_objects_v2(Bucket=VOLUME_BUCKET)
    results = []

    if "Contents" not in objects:
        return []

    for obj in objects["Contents"]:
        key = obj["Key"]
        content = s3.get_object(Bucket=VOLUME_BUCKET, Key=key)
        data = json.loads(content["Body"].read())
        results.append(data)

    return results


def save_volume(volume_data):
    key = f"{volume_data['id']}.json"
    s3.put_object(
        Bucket=VOLUME_BUCKET,
        Key=key,
        Body=json.dumps(volume_data),
        ContentType="application/json",
    )


def delete_volume(volume_id):
    key = f"{volume_id}.json"
    s3.delete_object(Bucket=VOLUME_BUCKET, Key=key)


def list_backups():
    """Return all backup metadata from MinIO's backup bucket."""
    objects = s3.list_objects_v2(Bucket=BACKUP_BUCKET)
    results = []

    if "Contents" not in objects:
        return []

    for obj in objects["Contents"]:
        key = obj["Key"]
        content = s3.get_object(Bucket=BACKUP_BUCKET, Key=key)
        data = json.loads(content["Body"].read())
        results.append(data)

    return results


def get_volume_by_name(name):
    vols = list_volumes()
    for v in vols:
        if v.get("name") == name:
            return v
    return None


def save_backup(backup_data):
    key = f"{backup_data['backup_id']}.json"
    s3.put_object(
        Bucket=BACKUP_BUCKET,
        Key=key,
        Body=json.dumps(backup_data),
        ContentType="application/json",
    )


# -----------------------------
# Prometheus Metrics (in-memory)
# -----------------------------
backup_operations_total = 0
backup_failures_total = 0

# -----------------------------
# API Endpoints
# -----------------------------

# GET: List all volumes
@app.route("/api/v1/volumes", methods=["GET"])
def api_get_volumes():
    volumes = list_volumes()
    return jsonify({"count": len(volumes), "volumes": volumes})


# POST: Create a new volume
@app.route("/api/v1/volumes", methods=["POST"])
def api_create_volume():
    body = request.get_json()

    if "name" not in body or "size_gb" not in body:
        return jsonify({"error": "Missing 'name' or 'size_gb'"}), 400

    vol_id = f"vol-{uuid.uuid4().hex[:8]}"

    volume_data = {
        "id": vol_id,
        "name": body["name"],
        "size_gb": body["size_gb"],
        "status": "available",
    }

    save_volume(volume_data)
    return jsonify(volume_data), 201


# DELETE: Remove a volume
@app.route("/api/v1/volumes/<volume_id>", methods=["DELETE"])
def api_delete_volume(volume_id):
    delete_volume(volume_id)
    return jsonify({"status": "deleted", "id": volume_id})


# POST: Real Backup Endpoint
@app.route("/api/v1/backup", methods=["POST"])
def api_backup_volume():
    """Create a real backup copy of the volume metadata."""
    global backup_operations_total, backup_failures_total

    body = request.get_json() or {}
    vol_name = body.get("volume")

    if not vol_name:
        backup_failures_total += 1
        return jsonify({"error": "Missing 'volume'"}), 400

    vol = get_volume_by_name(vol_name)
    if not vol:
        backup_failures_total += 1
        return jsonify({"error": "Volume not found", "volume": vol_name}), 404

    backup_id = f"{vol['id']}_bkp_{uuid.uuid4().hex[:6]}"

    backup_data = {
        "backup_id": backup_id,
        "volume_id": vol["id"],
        "volume_name": vol["name"],
        "size_gb": vol["size_gb"],
        "created_at": datetime.utcnow().isoformat() + "Z",
        "status": "completed",
    }

    try:
        save_backup(backup_data)
        backup_operations_total += 1
        return jsonify({"status": "backup_completed", **backup_data}), 200
    except Exception as e:
        backup_failures_total += 1
        return jsonify({"error": "backup_failed", "details": str(e)}), 500


# NEW: GET /api/v1/backups
@app.route("/api/v1/backups", methods=["GET"])
def api_list_backups():
    backups = list_backups()
    return jsonify({"count": len(backups), "backups": backups})


# -----------------------------
# Health & Metrics
# -----------------------------
@app.route("/health")
def api_health():
    return jsonify({"status": "ok"})


@app.route("/metrics")
def api_metrics():
    count = len(list_volumes())
    metrics_text = [
        f"storage_volumes_total {count}",
        f"backup_operations_total {backup_operations_total}",
        f"backup_failures_total {backup_failures_total}",
    ]
    return "\n".join(metrics_text) + "\n", 200


# -----------------------------
# Run Application
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
