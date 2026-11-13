import os
import time
import uuid
import datetime
import hmac
import hashlib
import sqlite3
import json
from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.responses import HTMLResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, ValidationError

app = FastAPI(title="ETBV Bounded Approval & Ingestion Gate")
DB_PATH = "/data/data/com.termux/files/home/monetization_vault.db"
api_key_header = APIKeyHeader(name="X-API-Token", auto_error=True)

GATE_SECRET = os.urandom(32)
NONCE_TTL_SECONDS = 5.0
MAX_WIRE_BYTES = 4096

class ArbitragePayload(BaseModel):
    source_market: str
    target_market: str
    asset_pair: str
    spread_percentage: float
    ask_price: float
    bid_price: float

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
            bid_price REAL,
            gated_nonce TEXT
        )
    """)
    # Migrate existing table if gated_nonce column is absent
    cursor.execute("PRAGMA table_info(arbitrage_feeds)")
    cols = [row[1] for row in cursor.fetchall()]
    if "gated_nonce" not in cols:
        cursor.execute("ALTER TABLE arbitrage_feeds ADD COLUMN gated_nonce TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approved_nonces (
            nonce TEXT PRIMARY KEY,
            payload_hmac TEXT NOT NULL,
            expires_at REAL NOT NULL
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS keys (token TEXT UNIQUE)")
    # Revoke legacy hardcoded public token
    cursor.execute("DELETE FROM keys WHERE token = 'ETB_SECURE_TOKEN_99X'")

    master_token = os.getenv("ETB_MASTER_TOKEN")
    if master_token:
        cursor.execute("INSERT OR IGNORE INTO keys (token) VALUES (?)", (master_token,))
    conn.commit()
    conn.close()

async def read_bounded_stream(request: Request, max_bytes: int = MAX_WIRE_BYTES) -> bytes:
    chunks = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="DROP: STREAM_EXCEEDED_4096_BYTES")
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="DROP: EMPTY_WIRE_STREAM")
    return b"".join(chunks)

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
    raw_bytes = await read_bounded_stream(request)
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
        payload = ArbitragePayload(**data)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
        raise HTTPException(status_code=400, detail="DROP: SCHEMA_CONTRACT_VIOLATION")
    if payload.ask_price <= 0 or payload.bid_price <= 0 or not (-100.0 <= payload.spread_percentage <= 100.0):
        raise HTTPException(status_code=400, detail="DROP: NUMERIC_INVARIANT_VIOLATION")

    now = time.monotonic()
    nonce = os.urandom(16).hex()
    expires_at = now + NONCE_TTL_SECONDS
    msg = raw_bytes + b"|" + nonce.encode("utf-8")
    approval_hmac = hmac.new(GATE_SECRET, msg, hashlib.sha256).hexdigest()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM approved_nonces WHERE expires_at < ?", (now,))
    cursor.execute(
        "INSERT INTO approved_nonces (nonce, payload_hmac, expires_at) VALUES (?, ?, ?)",
        (nonce, approval_hmac, expires_at)
    )
    conn.commit()
    conn.close()

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
    # Read bounded stream first so slow-body delivery cannot bypass the commit deadline
    raw_bytes = await read_bounded_stream(request)
    expected_msg = raw_bytes + b"|" + x_etbv_nonce.encode("utf-8")
    expected_hmac = hmac.new(GATE_SECRET, expected_msg, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hmac, x_etbv_hmac):
        raise HTTPException(status_code=403, detail="DROP: PAYLOAD_HMAC_MISMATCH")

    payload = ArbitragePayload(**json.loads(raw_bytes.decode("utf-8")))

    # Single durable transaction: verify deadline, consume nonce, and insert row atomically
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT payload_hmac, expires_at FROM approved_nonces WHERE nonce = ?", (x_etbv_nonce,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("ROLLBACK")
            raise HTTPException(status_code=403, detail="DROP: REPLAY_OR_UNKNOWN_NONCE")

        stored_hmac, expires_at = row
        commit_time = time.monotonic()
        if commit_time > expires_at:
            cursor.execute("DELETE FROM approved_nonces WHERE nonce = ?", (x_etbv_nonce,))
            cursor.execute("COMMIT")
            raise HTTPException(status_code=403, detail="DROP: COMMIT_DEADLINE_EXPIRED")

        if not hmac.compare_digest(stored_hmac, x_etbv_hmac):
            cursor.execute("ROLLBACK")
            raise HTTPException(status_code=403, detail="DROP: STORED_DIGEST_MISMATCH")

        cursor.execute("DELETE FROM approved_nonces WHERE nonce = ?", (x_etbv_nonce,))
        cursor.execute(
            "INSERT INTO arbitrage_feeds (source_market, target_market, asset_pair, spread_percentage, ask_price, bid_price, gated_nonce) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (payload.source_market, payload.target_market, payload.asset_pair, payload.spread_percentage, payload.ask_price, payload.bid_price, x_etbv_nonce)
        )
        cursor.execute("COMMIT")
    except HTTPException:
        raise
    except Exception as exc:
        cursor.execute("ROLLBACK")
        raise HTTPException(status_code=500, detail=f"DROP: ATOMIC_TX_FAILED ({exc})")
    finally:
        conn.close()

    return {"status": "COMMITTED_WITHIN_DEADLINE", "nonce": x_etbv_nonce}

@app.get("/api/v1/daas/valuations")
async def fetch_premium_metrics(token: str = Depends(verify_db_token)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, source_market, target_market, asset_pair, spread_percentage, ask_price, bid_price, gated_nonce FROM arbitrage_feeds")
    rows = cursor.fetchall()
    conn.close()
    return rows

@app.get("/api/v1/stix/bundle")
async def fetch_live_stix_bundle(token: str = Depends(verify_db_token)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, source_market, target_market, asset_pair, spread_percentage, ask_price, bid_price, gated_nonce FROM arbitrage_feeds")
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
            "bid_price": r[6],
            "provenance": "GATED_HMAC_COMMIT" if r[7] else "LEGACY_PRE_GATE"
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

@app.get("/api/v1/audit/snapshot")
async def fetch_signed_audit_snapshot(token: str = Depends(verify_db_token)):
    snapshot_path = "verification/artifacts/etbv_full_audit_snapshot.json"
    if not os.path.exists(snapshot_path):
        raise HTTPException(status_code=404, detail="AUDIT_SNAPSHOT_NOT_FOUND")
    with open(snapshot_path, "r") as f:
        return json.load(f)

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, source_market, target_market, asset_pair, spread_percentage, ask_price, bid_price, gated_nonce FROM arbitrage_feeds ORDER BY id DESC LIMIT 25")
    rows = cursor.fetchall()
    conn.close()

    table_rows = "".join(
        f"<tr><td>{r[0]}</td><td><strong>{r[3]}</strong></td><td>{r[1]}</td><td>{r[2]}</td>"
        f"<td>${r[5]:,.2f}</td><td>${r[6]:,.2f}</td><td style='color:#22c55e;'>+{r[4]}%</td>"
Use code with caution.
f"{'GATED' if r[7] else 'LEGACY'}"
for r in rows
)
return f"""



ETBV Bounded Gate Ledger


body {{ background:#0b0f19; color:#e2e8f0; font-family:monospace; padding:20px; }}
h1 {{ color:#38bdf8; font-size:18px; }}
table {{ width:100%; border-collapse:collapse; background:#111827; }}
th, td {{ padding:8px 10px; border-bottom:1px solid #1f2937; text-align:left; font-size:12px; }}
th {{ background:#1e293b; color:#94a3b8; }}



ETBV Bounded Approval & Ingestion Ledger
{table_rows}

ID	Pair	Source	Target	Ask	Bid	Spread	Provenance

"""
if name == "main":
import uvicorn
uvicorn.run(app, host="127.0.0.1", port=8000)
uuid4()}",
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

@app.get("/api/v1/audit/snapshot")
async def fetch_signed_audit_snapshot(token: str = Depends(verify_db_token)):
    snapshot_path = "verification/artifacts/etbv_full_audit_snapshot.json"
    if not os.path.exists(snapshot_path):
        raise HTTPException(status_code=404, detail="AUDIT_SNAPSHOT_NOT_FOUND")
    with open(snapshot_path, "r") as f:
        return json.load(f)

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, source_market, target_market, asset_pair, spread_percentage, ask_price, bid_price, gated_nonce FROM arbitrage_feeds ORDER BY id DESC LIMIT 25")
    rows = cursor.fetchall()
    conn.close()

    table_rows = "".join(
        f"<tr><td>{r[0]}</td><td><strong>{r[3]}</strong></td><td>{r[1]}</td><td>{r[2]}</td>"
        f"<td>${r[5]:,.2f}</td><td>${r[6]:,.2f}</td><td style='color:#22c55e;'>+{r[4]}%</td>"
        f"<td>{'GATED' if r[7] else 'LEGACY'}</td></tr>"
        for r in rows
    )
    return f"""<!DOCTYPE html><html><head><title>ETBV Bounded Gate Ledger</title><meta http-equiv="refresh" content="15">
<style>body{{background:#0b0f19;color:#e2e8f0;font-family:monospace;padding:20px}}h1{{color:#38bdf8;font-size:18px}}
table{{width:100%;border-collapse:collapse;background:#111827}}th,td{{padding:8px 10px;border-bottom:1px solid #1f2937;text-align:left;font-size:12px}}
th{{background:#1e293b;color:#94a3b8}}</style></head><body><h1>ETBV Bounded Approval & Ingestion Ledger</h1>
<table><thead><tr><th>ID</th><th>Pair</th><th>Source</th><th>Target</th><th>Ask</th><th>Bid</th><th>Spread</th><th>Provenance</th></tr></thead>
<tbody>{table_rows}</tbody></table></body></html>"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
