import json
import urllib.request
from etbv_client import ETBVClient

def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "ETBV-ThreatIntel/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))

def ingest_latest_cves(limit: int = 2):
    kev_url = "https://" + "www.cisa.gov" + "/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    data = fetch_json(kev_url)
    vulns = data.get("vulnerabilities", [])[-limit:]

    client = ETBVClient()
    for v in vulns:
        cve_id = v.get("cveID", "CVE-UNKNOWN")
        vendor = v.get("vendorProject", "UNKNOWN").upper().replace(" ", "_")
        product = v.get("product", "SYSTEM").upper().replace(" ", "_")

        # Route advisory telemetry through the identical single-use HMAC LayerZero gate
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
