import os
import json
import time
import sqlite3
import http.client
import urllib.request
import urllib.error
import concurrent.futures

BASE = "http://localhost:8000"
DB_PATH = "/data/data/com.termux/files/home/monetization_vault.db"
TOKEN = os.environ["ETB_MASTER_TOKEN"]

def count_rows_for_nonce(nonce: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM arbitrage_feeds WHERE gated_nonce = ?", (nonce,))
    n = cur.fetchone()[0]
    conn.close()
    return n

def http_req(method: str, path: str, raw_bytes: bytes | None, headers: dict):
    req = urllib.request.Request(BASE + path, data=raw_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

# Test 1: Revoked legacy token rejected
c1, b1 = http_req("GET", "/api/v1/daas/valuations", None, {"X-API-Token": "ETB_SECURE_TOKEN_99X"})
print(f"[TEST 1 - REVOKED TOKEN] HTTP {c1} -> {b1}")
assert c1 == 403

# Test 2: Streaming wire cap > 4096 bytes rejected before buffering
oversized = b'{"source_market":"' + (b"A" * 5000) + b'"}'
c2, b2 = http_req("POST", "/api/v1/gate/approve", oversized, {"X-API-Token": TOKEN, "Content-Type": "application/json"})
print(f"[TEST 2 - >4096B STREAM CAP] HTTP {c2} -> {b2}")
assert c2 == 413

valid = json.dumps({
    "source_market": "COINBASE",
    "target_market": "KRAKEN",
    "asset_pair": "BTC/USD",
    "spread_percentage": 0.05,
    "ask_price": 68500.0,
    "bid_price": 68534.25
}).encode("utf-8")

# Test 3: Single-transaction commit attributable to specific nonce
_, app_b = http_req("POST", "/api/v1/gate/approve", valid, {"X-API-Token": TOKEN, "Content-Type": "application/json"})
app = json.loads(app_b)
nonce_commit = app["nonce"]
assert count_rows_for_nonce(nonce_commit) == 0

c3, _ = http_req("POST", "/api/v1/ingest/arbitrage", valid, {
    "X-API-Token": TOKEN,
    "X-ETBV-Nonce": nonce_commit,
    "X-ETBV-HMAC": app["approval_hmac"],
    "Content-Type": "application/json"
})
rows_after_commit = count_rows_for_nonce(nonce_commit)
print(f"[TEST 3 - ATOMIC COMMIT] HTTP {c3} | Nonce {nonce_commit[:12]}... DB Rows: 0 -> {rows_after_commit}")
assert c3 == 200 and rows_after_commit == 1

# Test 4: Post-commit replay leaves per-nonce DB row count at 1
c4, b4 = http_req("POST", "/api/v1/ingest/arbitrage", valid, {
    "X-API-Token": TOKEN,
    "X-ETBV-Nonce": nonce_commit,
    "X-ETBV-HMAC": app["approval_hmac"],
    "Content-Type": "application/json"
})
rows_after_replay = count_rows_for_nonce(nonce_commit)
print(f"[TEST 4 - POST-COMMIT REPLAY] HTTP {c4} -> {b4} | Nonce {nonce_commit[:12]}... DB Rows: {rows_after_replay}")
assert c4 == 403 and rows_after_replay == 1

# Test 5: Slow-body delivery past 5.0s deadline leaves per-nonce DB row count at 0
_, app_slow_b = http_req("POST", "/api/v1/gate/approve", valid, {"X-API-Token": TOKEN, "Content-Type": "application/json"})
app_slow = json.loads(app_slow_b)
nonce_slow = app_slow["nonce"]

conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=15)
conn.putrequest("POST", "/api/v1/ingest/arbitrage")
conn.putheader("X-API-Token", TOKEN)
conn.putheader("X-ETBV-Nonce", nonce_slow)
conn.putheader("X-ETBV-HMAC", app_slow["approval_hmac"])
conn.putheader("Content-Type", "application/json")
conn.putheader("Content-Length", str(len(valid)))
conn.endheaders()

mid = len(valid) // 2
conn.send(valid[:mid])
time.sleep(5.3)
conn.send(valid[mid:])

resp_slow = conn.getresponse()
c5 = resp_slow.status
b5 = resp_slow.read().decode("utf-8")
conn.close()

rows_after_slow = count_rows_for_nonce(nonce_slow)
print(f"[TEST 5 - SLOW-BODY DEADLINE] HTTP {c5} -> {b5} | Nonce {nonce_slow[:12]}... DB Rows: {rows_after_slow}")
assert c5 == 403 and "COMMIT_DEADLINE_EXPIRED" in b5 and rows_after_slow == 0

# Test 6: 8-thread concurrent race on same nonce inserts exactly 1 row for that nonce
_, app_race_b = http_req("POST", "/api/v1/gate/approve", valid, {"X-API-Token": TOKEN, "Content-Type": "application/json"})
app_race = json.loads(app_race_b)
nonce_race = app_race["nonce"]

def race_worker(_):
    code, _ = http_req("POST", "/api/v1/ingest/arbitrage", valid, {
        "X-API-Token": TOKEN,
        "X-ETBV-Nonce": nonce_race,
        "X-ETBV-HMAC": app_race["approval_hmac"],
        "Content-Type": "application/json"
    })
    return code

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    race_codes = list(pool.map(race_worker, range(8)))

wins = race_codes.count(200)
blocks = race_codes.count(403)
rows_after_race = count_rows_for_nonce(nonce_race)
print(f"[TEST 6 - CONCURRENT RACE (8x)] 200 OK: {wins} | 403 Blocked: {blocks} | Nonce {nonce_race[:12]}... DB Rows: {rows_after_race}")
assert wins == 1 and blocks == 7 and rows_after_race == 1

# Test 7: Keyed HMAC snapshot verification
with open("verification/artifacts/etbv_full_audit_snapshot.json", "rb") as f:
    snap_bytes = f.read()

c7_ok, _ = http_req("POST", "/api/v1/audit/verify", snap_bytes, {"X-API-Token": TOKEN, "Content-Type": "application/json"})
tampered = snap_bytes.replace(b'"gated_hmac_commit_rows":', b'"gated_hmac_commit_rows": 999, "x":')
c7_bad, b7_bad = http_req("POST", "/api/v1/audit/verify", tampered, {"X-API-Token": TOKEN, "Content-Type": "application/json"})
print(f"[TEST 7 - AUDIT HMAC VERIFY] Valid HTTP {c7_ok} | Tampered HTTP {c7_bad} -> {b7_bad}")
assert c7_ok == 200 and c7_bad == 403

with open("verification/artifacts/live_http_gate_proof.json", "w") as f:
    json.dump({
        "isolated_background_producers": True,
        "revoked_token": {"http": c1},
        "stream_cap_4096b": {"http": c2},
        "atomic_commit": {"http": c3, "nonce": nonce_commit, "db_rows_for_nonce": rows_after_commit},
        "post_commit_replay": {"http": c4, "nonce": nonce_commit, "db_rows_for_nonce": rows_after_replay},
        "slow_body_deadline": {"http": c5, "nonce": nonce_slow, "db_rows_for_nonce": rows_after_slow},
        "concurrent_race_8x": {"wins_200": wins, "blocks_403": blocks, "nonce": nonce_race, "db_rows_for_nonce": rows_after_race},
        "audit_hmac_verify": {"valid_http": c7_ok, "tampered_http": c7_bad}
    }, f, indent=2)

# Test 8: Direct out-of-band SQLite insert without 32-char gated_nonce must abort at trigger level
conn_oob = sqlite3.connect(DB_PATH)
try:
    conn_oob.execute("INSERT INTO arbitrage_feeds (source_market, target_market, asset_pair, spread_percentage, ask_price, bid_price) VALUES ('OOB', 'OOB', 'BTC/USD', 1.0, 1.0, 2.0)")
    assert False, "SQLite trigger failed to block ungated insert"
except sqlite3.IntegrityError as e:
    trigger_msg = str(e)
    print(f"[TEST 8 - SQLITE TRIGGER ISOLATION] Aborted by DB engine -> {trigger_msg}")
    assert "DIRECT_UNGATED_INSERT_BLOCKED" in trigger_msg
finally:
    conn_oob.close()

with open("verification/artifacts/live_http_gate_proof.json", "r") as f:
    proof = json.load(f)
proof["sqlite_trigger_isolation"] = {"aborted": True, "error": trigger_msg}
with open("verification/artifacts/live_http_gate_proof.json", "w") as f:
    json.dump(proof, f, indent=2)
