import os
import json
import time
import datetime
import traceback
import urllib.request
import urllib.error
from scanner_producer import scan_all_pairs
from threat_intel_producer import ingest_latest_cves
from n8n_telemetry_bridge import fetch_verified_vault_rows, build_stix_bundle, dispatch_to_n8n, N8N_WEBHOOK_URL
from export_audit_snapshot import generate_audit_snapshot

POLL_SECONDS = float(os.getenv("ETBV_POLL_SECONDS", "60"))
ALERT_SPREAD_THRESHOLD = float(os.getenv("ETBV_ALERT_SPREAD_PCT", "0.05"))
ALERT_WEBHOOK_URL = os.getenv("ETBV_ALERT_WEBHOOK", N8N_WEBHOOK_URL)

def dispatch_priority_alert(alerts: list):
    if not alerts:
        return
    payload = json.dumps({
        "alert_type": "ETBV_LAYERZERO_PRIORITY_TRIGGER",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "count": len(alerts),
        "events": alerts
    }).encode("utf-8")
    req = urllib.request.Request(
        ALERT_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"[PRIORITY ALERT] Dispatched {len(alerts)} priority triggers -> HTTP {resp.status}", flush=True)
    except urllib.error.URLError:
        with open("verification/artifacts/latest_priority_alerts.json", "w") as f:
            f.write(payload.decode("utf-8"))
        print(f"[PRIORITY ALERT] Logged {len(alerts)} triggers to verification/artifacts/latest_priority_alerts.json", flush=True)

def run_loop():
    token = os.environ["ETB_MASTER_TOKEN"]
    seen_alert_ids = set()
    print(f"[DAEMON] Starting ETBV Dual-Feed Pipeline Loop (interval: {POLL_SECONDS}s, alert threshold: {ALERT_SPREAD_THRESHOLD}%)...", flush=True)
    while True:
        try:
            scan_all_pairs(min_spread_pct=0.001)
            ingest_latest_cves(limit=2)
            rows = fetch_verified_vault_rows(token)

            new_alerts = []
            for r in rows:
                row_id, source_mkt, target_mkt, asset_pair, spread_pct, ask_px, bid_px, gated_nonce = r
                if row_id in seen_alert_ids:
                    continue
                seen_alert_ids.add(row_id)
                if str(asset_pair).startswith("CVE-") or float(spread_pct) >= ALERT_SPREAD_THRESHOLD:
                    new_alerts.append({
                        "vault_id": row_id,
                        "source": source_mkt,
                        "target": target_mkt,
                        "asset_pair": str(asset_pair),
                        "spread_percentage": float(spread_pct)
                    })

            dispatch_priority_alert(new_alerts)
            bundle = build_stix_bundle(rows)
            dispatch_to_n8n(bundle, N8N_WEBHOOK_URL)
            generate_audit_snapshot()
        except Exception as exc:
            print(f"[DAEMON ERROR] {exc}", flush=True)
            traceback.print_exc()
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    run_loop()
