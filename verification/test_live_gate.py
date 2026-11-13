import os, json, sqlite3, urllib.request, urllib.error

BASE = "http://localhost:8000"
DB_PATH = "/data/data/com.termux/files/home/monetization_vault.db"
TOKEN = os.environ["ETB_MASTER_TOKEN"]

def db_row_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM arbitrage_feeds")
    n = c.fetchone()[0]
    conn.close()
    return n

def http_req(method: str, path: str, raw_bytes: bytes | None, headers: dict):
    req = urllib.request.Request(BASE + path, data=raw_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

c1, b1 = http_req("GET", "/api/v1/daas/valuations", None, {"X-API-Token": "ETB_SECURE_TOKEN_99X"})
print(f"[TEST 1 - REVOKED TOKEN] HTTP {c1} -> {b1}")
assert c1 == 403

oversized = b'{"source_market":"' + (b"A" * 5000) + b'"}'
c2, b2 = http_req("POST", "/api/v1/gate/approve", oversized, {"X-API-Token": TOKEN, "Content-Type": "application/json"})
print(f"[TEST 2 - >4096B STREAM CAP] HTTP {c2} -> {b2}")
assert c2 == 413

valid = json.dumps({"source_market":"COINBASE","target_market":"KRAKEN","asset_pair":"BTC/USD","spread_percentage":0.05,"ask_price":68500.0,"bid_price":68534.25}).encode()
before = db_row_count()
_, app_b = http_req("POST", "/api/v1/gate/approve", valid, {"X-API-Token": TOKEN, "Content-Type": "application/json"})
app = json.loads(app_b)

c3, _ = http_req("POST", "/api/v1/ingest/arbitrage", valid, {"X-API-Token": TOKEN, "X-ETBV-Nonce": app["nonce"], "X-ETBV-HMAC": app["approval_hmac"], "Content-Type": "application/json"})
after = db_row_count()
print(f"[TEST 3 - ATOMIC COMMIT] HTTP {c3} | DB Rows: {before} -> {after}")
assert c3 == 200 and after == before + 1

c4, b4 = http_req("POST", "/api/v1/ingest/arbitrage", valid, {"X-API-Token": TOKEN, "X-ETBV-Nonce": app["nonce"], "X-ETBV-HMAC": app["approval_hmac"], "Content-Type": "application/json"})
after_rep = db_row_count()
print(f"[TEST 4 - POST-COMMIT REPLAY] HTTP {c4} -> {b4} | DB Rows: {after_rep} (Unchanged)")
assert c4 == 403 and after_rep == after

with open("verification/artifacts/live_http_gate_proof.json", "w") as f:
    json.dump({"revoked_token": c1, "stream_cap": c2, "atomic_commit": {"http": c3, "before": before, "after": after}, "post_commit_replay": {"http": c4, "after": after_rep}}, f, indent=2)
