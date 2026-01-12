#!/usr/bin/env bash

# Define PATH explicitly to ensure cron can find binaries (curl, jq, etc.)
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Exit on error, undefined variables, and pipe failures
set -euo pipefail

# =====================================================
# CONFIGURATION
# =====================================================
# Get environment variables with defaults
API_BASE="${API_BASE:-http://storage-api:5000/api/v1}"
READ_TOKEN="${READ_TOKEN:-read-secret}"
BACKUP_TOKEN="${BACKUP_TOKEN:-backup-secret}"
LOG_FILE="/var/log/cron.log"

# Ensure the log file exists and is writable
touch "${LOG_FILE}" || true

log() {
  # Write to log file and stdout for 'docker logs' visibility
  echo "$1" >> "${LOG_FILE}"
  echo "$1"
}

log "========================================"
log "[cron] Backup job STARTED at $(date)"
log "[cron] Target API_BASE=${API_BASE}"

# =====================================================
# FETCH VOLUMES (READ TOKEN REQUIRED)
# =====================================================
log "[backup] Fetching volume list from ${API_BASE}/volumes ..."

# Execute curl and capture HTTP status code
HTTP_RESPONSE="$(curl -sS \
  -H "Accept: application/json" \
  -H "X-API-TOKEN: ${READ_TOKEN}" \
  -w 'HTTPSTATUS:%{http_code}' \
  "${API_BASE}/volumes" || echo "HTTPSTATUS:500")"

# Parse body and status code
BODY="$(echo "${HTTP_RESPONSE}" | sed 's/HTTPSTATUS:.*//')"
STATUS="$(echo "${HTTP_RESPONSE}" | sed -n 's/.*HTTPSTATUS://p')"

if [[ "${STATUS}" != "200" ]]; then
  log "[ERROR] Failed to fetch volumes (HTTP ${STATUS})"
  log "[ERROR] Response: ${BODY}"
  log "[cron] Backup job ABORTED"
  exit 1
fi

# Validate if the body is valid JSON before processing
if ! echo "${BODY}" | jq . >/dev/null 2>&1; then
    log "[ERROR] API returned invalid JSON content"
    exit 1
fi

VOLUME_COUNT="$(echo "${BODY}" | jq '.count // 0')"

if [[ "${VOLUME_COUNT}" -eq 0 ]]; then
  log "[backup] No volumes found in the system. Nothing to back up."
  log "[cron] Backup job FINISHED"
  exit 0
fi

log "[backup] Found ${VOLUME_COUNT} volumes to process"

# =====================================================
# TRIGGER BACKUPS (BACKUP TOKEN REQUIRED)
# =====================================================
FAILED=0
TOTAL=0

# Safely iterate through the JSON array using jq -c
while read -r vol; do
  # Skip empty lines
  [ -z "$vol" ] && continue
  
  VOL_NAME="$(echo "${vol}" | jq -r '.name')"
  VOL_ID="$(echo "${vol}" | jq -r '.id // "unknown"')"

  TOTAL=$((TOTAL+1))
  log "[backup] ($TOTAL/$VOLUME_COUNT) Processing: ${VOL_NAME} (ID: ${VOL_ID})"

  # Trigger the backup endpoint
  #BACKUP_RESPONSE="$(curl -sS \
  #  -H "X-API-TOKEN: ${BACKUP_TOKEN}" \
  #  -H "Content-Type: application/json" \
  #  -X POST "${API_BASE}/backup" \
  #  -d "{\"volume\":\"${VOL_NAME}\"}" \
  #  -w 'HTTPSTATUS:%{http_code}' || echo "HTTPSTATUS:500")"

  BACKUP_RESPONSE="$(curl -sS -w 'HTTPSTATUS:%{http_code}' \
  -X POST "${API_BASE}/backup" \
  -H "X-API-TOKEN: ${BACKUP_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"volume\":\"${VOL_ID}\"}" \
  || true)"  

  B_STATUS="$(echo "${BACKUP_RESPONSE}" | sed -n 's/.*HTTPSTATUS://p')"
  B_BODY="$(echo "${BACKUP_RESPONSE}" | sed 's/HTTPSTATUS:.*//')"

  if [[ "${B_STATUS}" != "200" && "${B_STATUS}" != "202" ]]; then
    log "[backup] FAILED: ${VOL_NAME} (HTTP ${B_STATUS})"
    log "[backup] Error Response: ${B_BODY}"
    FAILED=$((FAILED+1))
  else
    log "[backup] SUCCESS: ${VOL_NAME}"
  fi
done < <(echo "${BODY}" | jq -c '.volumes[]')

# =====================================================
# SUMMARY & EXIT
# =====================================================
log "[backup] Final Summary: total=${TOTAL}, failed=${FAILED}"
log "[cron] Backup job FINISHED at $(date)"
log "========================================"

# Exit with error status if any volume failed to backup
if [[ ${FAILED} -gt 0 ]]; then
    exit 1
fi

exit 0