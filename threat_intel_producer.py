import os
import json
import urllib.request
from etbv_client import ETBVClient

BASE_URL = "http://localhost:8000"

def fetch_json(url: str, headers: dict | None = None) -> dict | list:
    req_headers = {"User-Agent": "ETBV-ThreatIntel/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_existing_cves(api_token: str) -> set[str]:
    rows = fetch_json(f"{BASE_URL}/api/v1/daas/valuations", headers={"X-API-Token": api_token})
    return {r[3] for r in rows if isinstance(r, list) and len(r) > 3 and str(r[3]).startswith("CVE-")}

def ingest_latest_cves(limit: int = 2):
    api_token = os.environ["ETB_MASTER_TOKEN"]
    existing_cves = get_existing_cves(api_token)

    kev_url = "https://" + "www.cisa.gov" + "/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    data = fetch_json(kev_url)
    vulns = data.get("vulnerabilities", [])[-limit:]

    client = ETBVClient(api_token=api_token)
    for v in vulns:
        cve_id = v.get("cveID", "CVE-UNKNOWN")
        if cve_id in existing_cves:
            print(f"[THREAT INTEL] {cve_id} already verified in vault, skipping duplicate.", flush=True)
            continue

        vendor = v.get("vendorProject", "UNKNOWN").upper().replace(" ", "_")
        product = v.get("product", "SYSTEM").upper().replace(" ", "_")

        status, resp = client.submit_arbitrage_signal(
            source_market="CISA_KEV_FEED",
            target_market=f"{vendor}_{product}"[:32],
            asset_pair=cve_id,
            spread_percentage=10.0,
            ask_price=1.0,
            bid_price=1.1
        )
        print(f"[THREAT INTEL] {cve_id} ({vendor}) -> Gate HTTP {status} | {resp}", flush=True)

if __name__ == "__main__":
    ingest_latest_cves(limit=2)
