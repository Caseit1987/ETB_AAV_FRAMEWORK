#!/bin/bash
# RooTX Engine Production Deployment Script

PROJECT_DIR="$HOME/downloads/RooTX-patch-01"
BACKUP_DIR="$PROJECT_DIR/backups"
LOG_FILE="$PROJECT_DIR/rootx_backend.log"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "[*] Initializing production deployment lifecycle loop..."
cd "$PROJECT_DIR" || exit 1

# 1. Database Backup Configurations
if [ -f "rootx_persistence.db" ]; then
    mkdir -p "$BACKUP_DIR"
    echo "[*] Backing up persistence database layer..."
    cp "rootx_persistence.db" "$BACKUP_DIR/rootx_persistence_$TIMESTAMP.db"
fi

# 2. Log Rotation Automation Setup
if [ -f "$LOG_FILE" ] && [ $(wc -c < "$LOG_FILE") -gt 5242880 ]; then
    echo "[*] Rotating production log buffer (>5MB)..."
    mv "$LOG_FILE" "$LOG_FILE.$TIMESTAMP.old"
fi

# 3. Terminate stale application server threads safely
STALE_PID=$(pgrep -f "uvicorn main:app")
if [ -n "$STALE_PID" ]; then
    echo "[*] Shutting down active daemon process threads safely ($STALE_PID)..."
    kill -15 $STALE_PID
    sleep 2
fi

# 4. Fire up background maintenance daemons
echo "[*] Launching RooTX Backend Core Engine..."
nohup uvicorn main:app --host localhost --port 8000 >> "$LOG_FILE" 2>&1 &

# 5. Configure automated single-word terminal shortcut execution mappings
if ! grep -q "alias rootx-start" ~/.bashrc; then
    echo "[*] Registering shell bashrc shortcuts..."
    echo "alias rootx-start='$PROJECT_DIR/deploy.sh'" >> ~/.bashrc
    echo "alias rootx-logs='tail -f $LOG_FILE'" >> ~/.bashrc
fi

echo "[+] RooTX integration deployment baseline complete."
