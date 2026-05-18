#!/bin/bash

BASE_DIR="/data/data/com.termux/files/home/caseit2u2_lab"
BACKEND_APP="$BASE_DIR/backend_app.py"
ETB_GATE="$BASE_DIR/etb_gate.py"
DASHBOARD_APP="$BASE_DIR/SHADOW_DASHBOARD_FINAL.py"

case "$1" in
    start)
        echo "================================================================="
        echo "🌐 INITIALIZING CASEIT2U2 SECURE LABS ORCHESTRATION ENGINE..."
        echo "================================================================="
        fuser -k 8081/tcp >/dev/null 2>&1
        fuser -k 8082/tcp >/dev/null 2>&1
        fuser -k 8502/tcp >/dev/null 2>&1
        
        python3 "$BACKEND_APP" > "$BASE_DIR/backend.log" 2>&1 &
        echo "[+] Backend Application started (Listening on Port 8081)"
        
        python3 "$ETB_GATE" > "$BASE_DIR/gateway.log" 2>&1 &
        echo "[+] ETB AAV Validation Proxy started (Listening on Port 8082)"
        
        streamlit run "$DASHBOARD_APP" --server.port 8502 --server.fileWatcherType none > "$BASE_DIR/dashboard.log" 2>&1 &
        echo "[+] Streamlit UI Framework started (Hosting on Port 8502)"
        
        echo "-----------------------------------------------------------------"
        echo "[🚀 SYSTEM READY] Open browser view at http://localhost:8502"
        echo "================================================================="
        ;;
        
    stop)
        echo "================================================================="
        echo "🛑 TEARING DOWN PLATFORM APPLICATION INSTANCES..."
        echo "================================================================="
        fuser -k 8081/tcp >/dev/null 2>&1
        fuser -k 8082/tcp >/dev/null 2>&1
        fuser -k 8502/tcp >/dev/null 2>&1
        pkill -f "backend_app.py"
        pkill -f "etb_gate.py"
        pkill -f "SHADOW_DASHBOARD_FINAL.py"
        echo "[✓] Platform ecosystem completely offline."
        echo "================================================================="
        ;;
        
    status)
        echo "=== PLATFORM SERVICE MATRIX STATUS ==="
        pgrep -f "backend_app.py" >/dev/null && echo "Port 8081 (Backend App) : ONLINE" || echo "Port 8081 (Backend App) : OFFLINE"
        pgrep -f "etb_gate.py" >/dev/null && echo "Port 8082 (ETB Proxy)   : ONLINE" || echo "Port 8082 (ETB Proxy)   : OFFLINE"
        pgrep -f "SHADOW_DASHBOARD_FINAL.py" >/dev/null && echo "Port 8502 (Dashboard UI): ONLINE" || echo "Port 8502 (Dashboard UI): OFFLINE"
        ;;
        
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
