import os
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
TOKEN = os.environ["ETB_MASTER_TOKEN"]

def post_raw(path, raw_bytes, headers):
    req = urllib.request.Request(BASE + path, data=raw_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

valid_payload = json.dumps({
    "source_market": "BINANCE",
    "target_market": "COINBASE",
    "asset_pair": "BTC/USD",
    "spread_percentage": 0.45,
    "ask_price": 91200.0,
    "bid_price": 91610.6
}).encode("utf-8")

code, body = post_raw("/api/v1/gate/approve", valid_payload, {"X-API-Token": TOKEN, "Content-Type": "application/json"})
approval = json.loads(body)
print(f"[GATE] Status: {code} | Nonce: {approval.get('nonce')}")

mutated_payload = valid_payload.replace(b"91200.0", b"1.0")
code_toctou, body_toctou = post_raw("/api/v1/ingest/arbitrage", mutated_payload, {
    "X-API-Token": TOKEN,
    "X-ETBV-Nonce": approval["nonce"],
    "X-ETBV-HMAC": approval["approval_hmac"],
    "Content-Type": "application/json"
})
print(f"[TEST 1 - TOCTOU MUTATION] HTTP {code_toctou} -> {body_toctou}")

code_replay, body_replay = post_raw("/api/v1/ingest/arbitrage", valid_payload, {
    "X-API-Token": TOKEN,
    "X-ETBV-Nonce": approval["nonce"],
    "X-ETBV-HMAC": approval["approval_hmac"],
    "Content-Type": "application/json"
})
print(f"[TEST 2 - NONCE REPLAY] HTTP {code_replay} -> {body_replay}")

_, body2 = post_raw("/api/v1/gate/approve", valid_payload, {"X-API-Token": TOKEN, "Content-Type": "application/json"})
app2 = json.loads(body2)
code_ok, body_ok = post_raw("/api/v1/ingest/arbitrage", valid_payload, {
    "X-API-Token": TOKEN,
    "X-ETBV-Nonce": app2["nonce"],
    "X-ETBV-HMAC": app2["approval_hmac"],
    "Content-Type": "application/json"
})
print(f"[TEST 3 - ATOMIC EXECUTION] HTTP {code_ok} -> {body_ok}")

with open("verification/artifacts/live_http_gate_proof.json", "w") as f:
    json.dump({
        "toctou_block": {"http": code_toctou, "detail": body_toctou},
        "replay_block": {"http": code_replay, "detail": body_replay},
        "atomic_allow": {"http": code_ok, "detail": body_ok}
    }, f, indent=2)
