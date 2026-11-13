#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=== ETBV AAV LayerZero Framework Installer ==="

# 1. Install core Python dependencies
python3 -m pip install --quiet --upgrade fastapi uvicorn pydantic

# 2. Initialize .env with a unique cryptographic master token if missing
if [ ! -f .env ] || ! grep -q "^ETB_MASTER_TOKEN=" .env; then
  TOKEN=$(python3 -c 'import os; print(os.urandom(16).hex())')
  echo "ETB_MASTER_TOKEN=$TOKEN" >> .env
  echo "[INSTALL] Generated new ETB_MASTER_TOKEN in .env"
fi

# 3. Run pre-flight LayerZero non-bypassability verification suite
echo "[INSTALL] Running pre-flight boundary verification suite..."
python3 verification/bench_boundary_hardened.py >/dev/null
echo "[INSTALL] Non-bypassability verification PASSED."

# 4. Launch stack via start_etbv.sh
chmod +x start_etbv.sh
./start_etbv.sh start

echo "=== DEPLOYMENT COMPLETE ==="
echo "Dashboard: http://localhost:8000/dashboard"
echo "STIX API:  http://localhost:8000/api/v1/stix/bundle"
