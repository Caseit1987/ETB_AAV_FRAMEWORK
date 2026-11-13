#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE}")" && pwd)"
BACKUP_DIR="$DIR/backups"
DB_FILE="/data/data/com.termux/files/home/monetization_vault.db"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$BACKUP_DIR/monetization_vault_$STAMP.db"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# Safe online SQLite backup (respects active locks without corrupting WAL/transactions)
python3 -c "
import sqlite3
src = sqlite3.connect('$DB_FILE')
dst = sqlite3.connect('$OUT_FILE')
src.backup(dst)
dst.close()
src.close()
"
chmod 600 "$OUT_FILE"

# Retain only the 7 most recent snapshots
ls -1t "$BACKUP_DIR"/monetization_vault_*.db 2>/dev/null | tail -n +8 | xargs -r rm -f
echo "[BACKUP] Created safe online snapshot: $OUT_FILE (Retained latest 7)"
