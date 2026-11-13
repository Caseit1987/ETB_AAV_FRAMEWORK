import os
import time
import traceback
from scanner_producer import scan_all_pairs
from n8n_telemetry_bridge import fetch_verified_vault_rows, build_stix_bundle, dispatch_to_n8n, N8N_WEBHOOK_URL

POLL_SECONDS = float(os.getenv("ETBV_POLL_SECONDS", "60"))

def run_loop():
    token = os.environ["ETB_MASTER_TOKEN"]
    print(f"[DAEMON] Starting ETBV multi-pair pipeline loop (interval: {POLL_SECONDS}s)...", flush=True)
    while True:
        try:
            scan_all_pairs(min_spread_pct=0.001)
            rows = fetch_verified_vault_rows(token)
            bundle = build_stix_bundle(rows)
            dispatch_to_n8n(bundle, N8N_WEBHOOK_URL)
        except Exception as exc:
            print(f"[DAEMON ERROR] {exc}", flush=True)
            traceback.print_exc()
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    run_loop()
