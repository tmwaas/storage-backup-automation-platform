#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://storage-api:5000/api/v1}"
LOG_FILE="/var/log/cron.log"

echo "========================================" >> "${LOG_FILE}"
echo "[cron] Backup job STARTED at $(date)" >> "${LOG_FILE}"
echo "[cron] API_BASE=${API_BASE}" >> "${LOG_FILE}"

echo "[backup] Fetching volumes from ${API_BASE}/volumes ..." >> "${LOG_FILE}"
VOLUMES_JSON="$(curl -sS "${API_BASE}/volumes")"

# Get list of volume names
VOL_NAMES="$(echo "$VOLUMES_JSON" | jq -r '.volumes[].name')"

if [[ -z "${VOL_NAMES}" ]]; then
  echo "[backup] No volumes found. Exiting." >> "${LOG_FILE}"
  echo "[cron] Backup job FINISHED at $(date)" >> "${LOG_FILE}"
  exit 0
fi

FAILED=0
TOTAL=0

for v in ${VOL_NAMES}; do
  TOTAL=$((TOTAL+1))
  echo "[backup] Trigger backup for volume=${v} at $(date)" >> "${LOG_FILE}"

  if ! curl -sS -X POST "${API_BASE}/backup" \
      -H "Content-Type: application/json" \
      -d "{\"volume\":\"${v}\"}" >/dev/null; then
    echo "[backup] FAILED volume=${v}" >> "${LOG_FILE}"
    FAILED=$((FAILED+1))
  else
    echo "[backup] OK volume=${v}" >> "${LOG_FILE}"
  fi
done

echo "[backup] Summary: total=${TOTAL}, failed=${FAILED}" >> "${LOG_FILE}"
echo "[cron] Backup job FINISHED at $(date)" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"

exit 0
