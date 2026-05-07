#!/usr/bin/env bash
# Backup diario del SQLite de VAECOS Tracking en producción.
#
# Usa `sqlite3 .backup` (online backup API) — seguro mientras la app está
# corriendo en modo WAL, no bloquea writers. Comprime con gzip y rota.
#
# Cron: 0 3 * * * /opt/vaecos/scripts/backup_db.sh >> /var/log/vaecos-backup.log 2>&1
#
# Variables tunables:
#   DB_PATH         — ruta del SQLite vivo
#   BACKUP_DIR      — dónde guardar los .db.gz
#   RETENTION_DAYS  — cuántos días conservar (default 14)
set -euo pipefail

DB_PATH="${DB_PATH:-/opt/vaecos/data/vaecos_tracking.db}"
BACKUP_DIR="${BACKUP_DIR:-/opt/vaecos/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

ts="$(date -u +%Y%m%d_%H%M%S)"
tmp_file="${BACKUP_DIR}/.vaecos_${ts}.db"
out_file="${BACKUP_DIR}/vaecos_${ts}.db.gz"

mkdir -p "${BACKUP_DIR}"

echo "[$(date -u +%FT%TZ)] backup start: ${DB_PATH} -> ${out_file}"

# Online backup vía sqlite3 — WAL-safe, no bloquea la app.
sqlite3 "${DB_PATH}" ".backup '${tmp_file}'"

# Comprimir y mover atómico.
gzip -9 "${tmp_file}"
mv "${tmp_file}.gz" "${out_file}"

size_kb="$(du -k "${out_file}" | cut -f1)"
echo "[$(date -u +%FT%TZ)] backup ok: ${out_file} (${size_kb} KB)"

# Retención: borrar backups más viejos que N días.
deleted="$(find "${BACKUP_DIR}" -maxdepth 1 -name 'vaecos_*.db.gz' -mtime "+${RETENTION_DAYS}" -print -delete | wc -l)"
if [ "${deleted}" -gt 0 ]; then
  echo "[$(date -u +%FT%TZ)] retention: ${deleted} backup(s) older than ${RETENTION_DAYS} days deleted"
fi

# Sanity check: el último backup debería pesar >0 bytes.
if [ ! -s "${out_file}" ]; then
  echo "[$(date -u +%FT%TZ)] ERROR: backup file is empty" >&2
  exit 1
fi
