#!/bin/bash

# Get the current directory dynamically regardless of environment
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

case "$1" in
    start)
        echo "================================================================="
        echo "🌐 INITIALIZING CASEIT2U2 SECURE LABS ORCHESTRATION ENGINE..."
        echo "================================================================="
        
        # Start core modules relatively
        python3 "$BASE_DIR/backend_app.py" > "$BASE_DIR/backend.log" 2>&1 &
        python3 "$BASE_DIR/etb_gate.py" > "$BASE_DIR/gateway.log" 2>&1 &
        
        # Start Dashboard Engine
        streamlit run "$BASE_DIR/SHADOW_DASHBOARD_FINAL.py" --server.port 8503 --server.headless true > "$BASE_DIR/dashboard.log" 2>&1 &
        
        echo "[🚀 SYSTEM READY] Services initialized asynchronously."
        ;;
    stop)
        echo "[-] Shutting down Caseit2u2 environment processes..."
        pkill -f backend_app.py
        pkill -f etb_gate.py
        pkill -f SHADOW_DASHBOARD_FINAL.py
        echo "[+] Cleaned up active workspace channels."
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        exit 1
        ;;
esac
