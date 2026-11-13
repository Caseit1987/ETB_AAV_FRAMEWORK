#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE}")" && pwd)"
cd "$DIR"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

case "${1:-start}" in
  start)
    pkill -f "app_server.py" 2>/dev/null || true
    pkill -f "pipeline_daemon.py" 2>/dev/null || true

    nohup python3 app_server.py > daemon_output.log 2>&1 &
    for i in $(seq 1 25); do
      python3 -c 'import socket; s=socket.create_connection(("localhost", 8000), 0.2); s.close()' 2>/dev/null && break
      sleep 0.2
    done

    nohup python3 pipeline_daemon.py > pipeline_daemon.log 2>&1 &
    echo "[ETBV] LayerZero Gate (localhost:8000) and Multi-Pair Pipeline Daemon started."
    ;;
  stop)
    pkill -f "app_server.py" 2>/dev/null || true
    pkill -f "pipeline_daemon.py" 2>/dev/null || true
    echo "[ETBV] Stopped all ETBV background daemons."
    ;;
  status)
    pgrep -af "app_server.py|pipeline_daemon.py" || echo "[ETBV] No active ETBV daemons running."
    echo "--- Recent Pipeline Log ---"
    tail -n 10 pipeline_daemon.log 2>/dev/null || echo "No pipeline log yet."
    ;;
  *)
    echo "Usage: ./start_etbv.sh {start|stop|status}"
    exit 1
    ;;
esac
