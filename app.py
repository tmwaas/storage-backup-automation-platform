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
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin-secret")
BACKUP_TOKEN = os.getenv("BACKUP_TOKEN", "backup-secret")
READ_TOKEN = os.getenv("READ_TOKEN", "read-secret")


def check_token(required_role: str, endpoint: str) -> bool:
    token = request.headers.get("X-API-TOKEN")

    role_map = {
        ADMIN_TOKEN: "admin",
        BACKUP_TOKEN: "backup",
        READ_TOKEN: "read",
    }

    role = role_map.get(token)
    allowed = False

    if role == "admin":
        allowed = True
    elif required_role == "backup" and role in ["backup", "admin"]:
        allowed = True
    elif required_role == "read" and role in ["read", "backup", "admin"]:
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


def ensure_bucket(name: str):
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

# Backup based on volume_id & volume_name
backup_last_success_timestamp = Gauge(
    "backup_last_success_timestamp",
    "Last successful backup timestamp",
    ["volume_id", "volume_name"]
)

backup_success_total = Counter(
    "backup_success_total",
    "Total successful backups per volume",
    ["volume_id", "volume_name"]
)

backup_rpo_violation = Gauge(
    "backup_rpo_violation",
    "Backup RPO violation (1 = violation, 0 = OK)",
    ["volume_id", "volume_name"]
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
            s3.get_object(
                Bucket=VOLUME_BUCKET,
                Key=o["Key"]
            )["Body"].read()
        )
        for o in objects["Contents"]
    ]


def list_backups():
    objects = s3.list_objects_v2(Bucket=BACKUP_BUCKET)
    if "Contents" not in objects:
        return []

    return [
        json.loads(
            s3.get_object(
                Bucket=BACKUP_BUCKET,
                Key=o["Key"]
            )["Body"].read()
        )
        for o in objects["Contents"]
    ]


def get_volume_by_id(volume_id: str):
    return next((v for v in list_volumes() if v["id"] == volume_id), None)


def save_volume(volume: dict):
    s3.put_object(
        Bucket=VOLUME_BUCKET,
        Key=f"{volume['id']}.json",
        Body=json.dumps(volume),
        ContentType="application/json",
    )


def save_backup(backup: dict):
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

    body = request.get_json() or {}
    if "name" not in body or "size_gb" not in body:
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
    volume_id = body.get("volume")

    if not volume_id:
        backup_failures_total.inc()
        return jsonify({"error": "Missing volume_id"}), 400

    vol = get_volume_by_id(volume_id)
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
        backup_rpo_violation.labels(
            volume_id=vol["id"],
            volume_name=vol["name"]
        ).set(1)
        return jsonify({"error": str(e)}), 500

    # ✅ SUCCESS METRICS
    backup_operations_total.inc()
    backup_success_total.labels(
        volume_id=vol["id"],
        volume_name=vol["name"]
    ).inc()
    backup_last_success_timestamp.labels(
        volume_id=vol["id"],
        volume_name=vol["name"]
    ).set(time.time())
    backup_rpo_violation.labels(
        volume_id=vol["id"],
        volume_name=vol["name"]
    ).set(0)

    return jsonify(backup), 200


@app.route("/api/v1/volumes/<volume_id>", methods=["DELETE"])
def api_delete_volume(volume_id):
    if not check_token("admin", "/api/v1/volumes/<id>"):
        return jsonify({"error": "unauthorized"}), 403

    objects = s3.list_objects_v2(Bucket=VOLUME_BUCKET)
    if "Contents" not in objects:
        return jsonify({"error": "Volume not found"}), 404

    key = f"{volume_id}.json"
    keys = [o["Key"] for o in objects["Contents"]]

    if key not in keys:
        return jsonify({"error": "Volume not found"}), 404

    s3.delete_object(Bucket=VOLUME_BUCKET, Key=key)
    storage_volume_count.set(len(list_volumes()))

    return jsonify({
        "status": "deleted",
        "volume_id": volume_id
    }), 200


# =====================================================
# HEALTH & METRICS
# =====================================================
@app.route('/health')
def health_check():
    return {"status": "healthy"}, 200

@app.route("/metrics")
def api_metrics():
    storage_volume_count.set(len(list_volumes()))
    return generate_latest(), 200, {
        "Content-Type": CONTENT_TYPE_LATEST
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
