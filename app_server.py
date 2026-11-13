import os
import time
import uuid
import datetime
import hmac
import hashlib
import sqlite3
import json
from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, ValidationError

app = FastAPI(title="Eternal Trust Engine - LayerZero Hardened")
DB_PATH = "/data/data/com.termux/files/home/monetization_vault.db"
api_key_header = APIKeyHeader(name="X-API-Token", auto_error=True)

GATE_SECRET = os.urandom(32)
NONCE_TTL_SECONDS = 5.0
ACTIVE_NONCES = {}

class ArbitragePayload(BaseModel):
    source_market: str
    target_market: str
    asset_pair: str
    spread_percentage: float
    ask_price: float
    bid_price: float

def purge_expired_nonces(now: float):
    expired = [n for n, exp in ACTIVE_NONCES.items() if now > exp]
    for n in expired:
        del ACTIVE_NONCES[n]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS arbitrage_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_market TEXT,
            target_market TEXT,
            asset_pair TEXT,
            spread_percentage REAL,
            ask_price REAL,
            bid_price REAL
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS keys (token TEXT UNIQUE)")
    master_token = os.getenv("ETB_MASTER_TOKEN")
    if master_token:
        try:
            cursor.execute("INSERT INTO keys (token) VALUES (?)", (master_token,))
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()

def verify_db_token(token: str = Depends(api_key_header)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT token FROM keys WHERE token = ?", (token,))
    row = cursor.fetchone()
    conn.close()
    if not row or not hmac.compare_digest(row[0], token):
        raise HTTPException(status_code=403, detail="DROP: INVALID_API_TOKEN")
    return token

init_db()

@app.post("/api/v1/gate/approve")
async def gate_approve_payload(request: Request, token: str = Depends(verify_db_token)):
    now = time.monotonic()
    purge_expired_nonces(now)

    raw_bytes = await request.body()
    if not raw_bytes or len(raw_bytes) > 4096:
        raise HTTPException(status_code=400, detail="DROP: WIRE_FRAME_BOUNDARY_VIOLATION")
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
        payload = ArbitragePayload(**data)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
        raise HTTPException(status_code=400, detail="DROP: PRE_PARSER_CONTRACT_VIOLATION")
    if payload.ask_price <= 0 or payload.bid_price <= 0 or not (-100.0 <= payload.spread_percentage <= 100.0):
        raise HTTPException(status_code=400, detail="DROP: NUMERIC_INVARIANT_VIOLATION")

    nonce = os.urandom(16).hex()
    ACTIVE_NONCES[nonce] = now + NONCE_TTL_SECONDS
    msg = raw_bytes + b"|" + nonce.encode("utf-8")
    approval_hmac = hmac.new(GATE_SECRET, msg, hashlib.sha256).hexdigest()
    return {
        "status": "CONTRACT_APPROVED",
        "nonce": nonce,
        "approval_hmac": approval_hmac,
        "ttl_seconds": NONCE_TTL_SECONDS
    }

@app.post("/api/v1/ingest/arbitrage")
async def receive_arbitrage_signal(
    request: Request,
    x_etbv_nonce: str = Header(..., alias="X-ETBV-Nonce"),
    x_etbv_hmac: str = Header(..., alias="X-ETBV-HMAC"),
    token: str = Depends(verify_db_token)
):
    now = time.monotonic()
    expiry = ACTIVE_NONCES.pop(x_etbv_nonce, None)
    purge_expired_nonces(now)

    if expiry is None:
        raise HTTPException(status_code=403, detail="DROP: REPLAY_OR_INVALID_NONCE")
    if now > expiry:
        raise HTTPException(status_code=403, detail="DROP: NONCE_EXPIRED")

    raw_bytes = await request.body()
    expected_msg = raw_bytes + b"|" + x_etbv_nonce.encode("utf-8")
    expected_hmac = hmac.new(GATE_SECRET, expected_msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hmac, x_etbv_hmac):
        raise HTTPException(status_code=403, detail="DROP: TOCTOU_OR_FORGED_PAYLOAD")

    payload = ArbitragePayload(**json.loads(raw_bytes.decode("utf-8")))
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO arbitrage_feeds (source_market, target_market, asset_pair, spread_percentage, ask_price, bid_price) VALUES (?, ?, ?, ?, ?, ?)",
        (payload.source_market, payload.target_market, payload.asset_pair, payload.spread_percentage, payload.ask_price, payload.bid_price)
    )
    conn.commit()
    conn.close()
    return {"status": "VERIFIED_ATOMIC_EXECUTION"}

@app.get("/api/v1/daas/valuations")
async def fetch_premium_metrics(token: str = Depends(verify_db_token)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM arbitrage_feeds")
    rows = cursor.fetchall()
    conn.close()
    return rows

@app.get("/api/v1/stix/bundle")
async def fetch_live_stix_bundle(token: str = Depends(verify_db_token)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM arbitrage_feeds")
    rows = cursor.fetchall()
    conn.close()

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
