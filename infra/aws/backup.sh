#!/usr/bin/env bash
# Phase 13: daily backup - pg_dump of the production database plus an
# archive of the three persistent app-data directories (uploads, ML
# artifacts, RAG documents), so a full rollback to local-only (see
# ROLLBACK.md) never depends on the EC2 instance/EBS volume still existing
# for longer than this retention window. Runs ON THE EC2 INSTANCE, invoked
# by the eip-backup.timer systemd unit (see README.md step 9).
#
# Backups are written to /opt/eip/backups on the same EBS volume as the
# live data - this protects against container-level mistakes (e.g. an
# accidental `docker compose down -v`) and gives you a restorable snapshot
# for the rollback procedure, but NOT against loss of the volume/instance
# itself. Copying backups off-instance (e.g. to S3) was intentionally left
# out of this phase's locked decisions - worth adding later if you want
# durability beyond a single EBS volume.
set -euo pipefail

BACKUP_DIR="/opt/eip/backups"
DATA_DIR="/opt/eip/data"
COMPOSE_FILE="/opt/eip/docker-compose.prod.yml"
ENV_FILE="/opt/eip/.env.prod"
RETENTION_DAYS=14
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "${BACKUP_DIR}"

echo "[${TIMESTAMP}] Dumping database..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-eip_user}" -d "${POSTGRES_DB:-eip_prod}" \
  | gzip > "${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz"

echo "[${TIMESTAMP}] Archiving app data (uploads, ML artifacts, RAG documents)..."
tar -czf "${BACKUP_DIR}/appdata_${TIMESTAMP}.tar.gz" -C "${DATA_DIR}" app

echo "[${TIMESTAMP}] Pruning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -type f -mtime "+${RETENTION_DAYS}" -delete

echo "[${TIMESTAMP}] Done: $(ls -la "${BACKUP_DIR}" | grep "${TIMESTAMP}")"
