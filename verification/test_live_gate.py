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

import http.client
import time

# Test 6: Slow-body delivery past 5.0s commit deadline must fail at SQLite commit boundary with 0 DB effect
before_slow = db_row_count()
_, app_slow_b = http_req("POST", "/api/v1/gate/approve", valid, {"X-API-Token": TOKEN, "Content-Type": "application/json"})
app_slow = json.loads(app_slow_b)

conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=15)
conn.putrequest("POST", "/api/v1/ingest/arbitrage")
conn.putheader("X-API-Token", TOKEN)
conn.putheader("X-ETBV-Nonce", app_slow["nonce"])
conn.putheader("X-ETBV-HMAC", app_slow["approval_hmac"])
conn.putheader("Content-Type", "application/json")
conn.putheader("Content-Length", str(len(valid)))
conn.endheaders()

# Send first half of body immediately, stall 5.3s across the commit deadline, then send second half
mid = len(valid) // 2
conn.send(valid[:mid])
time.sleep(5.3)
conn.send(valid[mid:])

resp_slow = conn.getresponse()
c6 = resp_slow.status
b6 = resp_slow.read().decode("utf-8")
conn.close()

after_slow = db_row_count()
print(f"[TEST 6 - SLOW-BODY DEADLINE] HTTP {c6} -> {b6} | DB Rows: {after_slow} (Unchanged)")
assert c6 == 403 and "COMMIT_DEADLINE_EXPIRED" in b6 and after_slow == before_slow

with open("verification/artifacts/live_http_gate_proof.json", "r") as f:
    proof = json.load(f)
proof["slow_body_deadline_block"] = {"http": c6, "detail": b6, "db_rows_before": before_slow, "db_rows_after": after_slow}
with open("verification/artifacts/live_http_gate_proof.json", "w") as f:
    json.dump(proof, f, indent=2)
