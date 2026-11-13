import os
import json
import uuid
import datetime
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"
N8N_WEBHOOK_URL = os.getenv("ETBV_N8N_WEBHOOK", "http://localhost:5678/webhook/etbv-telemetry")

def fetch_verified_vault_rows(api_token: str) -> list:
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/daas/valuations",
        headers={"X-API-Token": api_token}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))

def build_stix_bundle(rows: list) -> dict:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    records = [
        {
            "id": r[0],
            "source_market": r[1],
            "target_market": r[2],
            "asset_pair": r[3],
            "spread_percentage": r[4],
            "ask_price": r[5],
            "bid_price": r[6]
        }
        for r in rows
    ]
    return {
        "type": "bundle",
        "id": f"bundle--{uuid.uuid4()}",
        "objects": [{
            "type": "observed-data",
            "spec_version": "2.1",
            "id": f"observed-data--{uuid.uuid4()}",
            "created": now_iso,
            "modified": now_iso,
            "first_observed": now_iso,
            "last_observed": now_iso,
            "number_observed": len(records),
            "x_etbv_verified_vault_feed": records
        }]
    }

def dispatch_to_n8n(bundle: dict, webhook_url: str):
    payload = json.dumps(bundle).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"[N8N DISPATCH] HTTP {resp.status} -> Delivered {bundle['objects'][0]['number_observed']} verified records.")
    except urllib.error.URLError as e:
        print(f"[N8N STANDBY] Webhook offline ({e.reason}). Saved local snapshot to verification/artifacts/latest_n8n_bundle.json")
        with open("verification/artifacts/latest_n8n_bundle.json", "w") as f:
            json.dump(bundle, f, indent=2)

if __name__ == "__main__":
    token = os.environ["ETB_MASTER_TOKEN"]
    rows = fetch_verified_vault_rows(token)
    bundle = build_stix_bundle(rows)
    dispatch_to_n8n(bundle, N8N_WEBHOOK_URL)
