from flask import Flask, jsonify, request
import boto3
import json
import uuid
import time
import os
from datetime import datetime
from prometheus_client import (
    Gauge,
    Counter,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

app = Flask(__name__)

# =====================================================
# RBAC CONFIGURATION (API TOKEN BASED)
# =====================================================
def check_token(required_role, endpoint):
    token = request.headers.get("X-API-TOKEN")

    role_map = {
        os.getenv("ADMIN_TOKEN"): "admin",
        os.getenv("BACKUP_TOKEN"): "backup",
        os.getenv("READ_TOKEN"): "read",
    }

    role = role_map.get(token)

    allowed = False
    if role == "admin":
        allowed = True
    elif required_role == "backup" and role == "backup":
        allowed = True
    elif required_role == "read" and role in ["read", "backup"]:
        allowed = True

    if not allowed:
        rbac_denied_requests_total.labels(
            endpoint=endpoint,
            required_role=required_role
        ).inc()

    return allowed

# =====================================================
# MINIO / S3 CONFIGURATION
# =====================================================
s3 = boto3.client(
    "s3",
    endpoint_url="http://minio:9000",
    aws_access_key_id="minio",
    aws_secret_access_key="minio123",
    region_name="us-east-1",
)

VOLUME_BUCKET = "storage-volumes"
BACKUP_BUCKET = "storage-volumes-backup"

def ensure_bucket(name):
    try:
        s3.head_bucket(Bucket=name)
    except Exception:
        s3.create_bucket(Bucket=name)

ensure_bucket(VOLUME_BUCKET)
ensure_bucket(BACKUP_BUCKET)

# =====================================================
# PROMETHEUS METRICS
# =====================================================
storage_volume_count = Gauge(
    "storage_volume_count",
    "Total number of storage volumes"
)

backup_operations_total = Counter(
    "backup_operations_total",
    "Total number of backup operations"
)

backup_failures_total = Counter(
    "backup_failures_total",
    "Total number of backup failures"
)

backup_last_success_timestamp = Gauge(
    "backup_last_success_timestamp",
    "Last successful backup timestamp",
    ["volume"]
)

backup_rpo_violation = Gauge(
    "backup_rpo_violation",
    "Backup RPO violation (1 = violation, 0 = OK)",
    ["volume"]
)

rbac_denied_requests_total = Counter(
    "rbac_denied_requests_total",
    "Total number of RBAC denied requests",
    ["endpoint", "required_role"]
)

# =====================================================
# HELPER FUNCTIONS
# =====================================================
def list_volumes():
    objects = s3.list_objects_v2(Bucket=VOLUME_BUCKET)
    if "Contents" not in objects:
        return []

    return [
        json.loads(
            s3.get_object(Bucket=VOLUME_BUCKET, Key=o["Key"])["Body"].read()
        )
        for o in objects["Contents"]
    ]

def list_backups():
    objects = s3.list_objects_v2(Bucket=BACKUP_BUCKET)
    if "Contents" not in objects:
        return []

    return [
        json.loads(
            s3.get_object(Bucket=BACKUP_BUCKET, Key=o["Key"])["Body"].read()
        )
        for o in objects["Contents"]
    ]

def get_volume_by_name(name):
    return next((v for v in list_volumes() if v["name"] == name), None)

def save_volume(volume):
    s3.put_object(
        Bucket=VOLUME_BUCKET,
        Key=f"{volume['id']}.json",
        Body=json.dumps(volume),
        ContentType="application/json",
    )

def save_backup(backup):
    s3.put_object(
        Bucket=BACKUP_BUCKET,
        Key=f"{backup['backup_id']}.json",
        Body=json.dumps(backup),
        ContentType="application/json",
    )

# =====================================================
# API ENDPOINTS
# =====================================================
@app.route("/api/v1/volumes", methods=["GET"])
def api_get_volumes():
    if not check_token("read", "/api/v1/volumes"):
        return jsonify({"error": "unauthorized"}), 403

    volumes = list_volumes()
    storage_volume_count.set(len(volumes))
    return jsonify({"count": len(volumes), "volumes": volumes})


@app.route("/api/v1/volumes", methods=["POST"])
def api_create_volume():
    if not check_token("admin", "/api/v1/volumes"):
        return jsonify({"error": "unauthorized"}), 403

    body = request.get_json()
    if not body or "name" not in body or "size_gb" not in body:
        return jsonify({"error": "Missing name or size_gb"}), 400

    volume = {
        "id": f"vol-{uuid.uuid4().hex[:8]}",
        "name": body["name"],
        "size_gb": body["size_gb"],
        "status": "available",
    }

    save_volume(volume)
    storage_volume_count.set(len(list_volumes()))
    return jsonify(volume), 201


@app.route("/api/v1/backups", methods=["GET"])
def api_get_backups():
    if not check_token("read", "/api/v1/backups"):
        return jsonify({"error": "unauthorized"}), 403

    backups = list_backups()
    return jsonify({"count": len(backups), "backups": backups})


@app.route("/api/v1/backup", methods=["POST"])
def api_backup_volume():
    if not check_token("backup", "/api/v1/backup"):
        return jsonify({"error": "unauthorized"}), 403

    body = request.get_json() or {}
    vol_name = body.get("volume")

    if not vol_name:
        backup_failures_total.inc()
        return jsonify({"error": "Missing volume"}), 400

    vol = get_volume_by_name(vol_name)
    if not vol:
        backup_failures_total.inc()
        return jsonify({"error": "Volume not found"}), 404

    backup = {
        "backup_id": f"{vol['id']}_bkp_{uuid.uuid4().hex[:6]}",
        "volume_id": vol["id"],
        "volume_name": vol["name"],
        "size_gb": vol["size_gb"],
        "created_at": datetime.utcnow().isoformat() + "Z",
        "status": "completed",
    }

    try:
        save_backup(backup)
    except Exception as e:
        backup_failures_total.inc()
        backup_rpo_violation.labels(volume=vol["name"]).set(1)
        return jsonify({"error": str(e)}), 500

    backup_operations_total.inc()
    backup_last_success_timestamp.labels(volume=vol["name"]).set(time.time())
    backup_rpo_violation.labels(volume=vol["name"]).set(0)

    return jsonify(backup), 200

# =====================================================
# HEALTH & METRICS
# =====================================================
@app.route("/health")
def api_health():
    return jsonify({"status": "ok"})


@app.route("/metrics")
def api_metrics():
    storage_volume_count.set(len(list_volumes()))
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
