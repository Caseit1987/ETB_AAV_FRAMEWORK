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

from fastapi.responses import HTMLResponse

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, source_market, target_market, asset_pair, spread_percentage, ask_price, bid_price FROM arbitrage_feeds ORDER BY id DESC LIMIT 25")
    rows = cursor.fetchall()
    conn.close()

    table_rows = "".join(
        f"<tr><td>{r[0]}</td><td><strong>{r[3]}</strong></td><td>{r[1]}</td><td>{r[2]}</td>"
        f"<td>${r[5]:,.2f}</td><td>${r[6]:,.2f}</td><td style='color:#22c55e;'>+{r[4]}%</td></tr>"
        for r in rows
    )

    pairs = sorted(list({r[3] for r in rows})) or ["BTC/USD", "ETH/USD", "SOL/USD"]
    sources = sorted(list({r[1] for r in rows} | {r[2] for r in rows})) or ["COINBASE", "KRAKEN"]

    nodes = [{"id": "GATE", "label": "ETBV LayerZero Gate", "group": "gate"}]
    nodes += [{"id": f"SRC_{s}", "label": s, "group": "source"} for s in sources]
    nodes += [{"id": f"PAIR_{p}", "label": p, "group": "pair"} for p in pairs]
    nodes.append({"id": "VAULT", "label": f"Vault DB ({len(rows)} Verified)", "group": "vault"})

    edges = [{"from": f"SRC_{s}", "to": "GATE", "label": "RAW_WIRE"} for s in sources]
    edges += [{"from": "GATE", "to": f"PAIR_{p}", "label": "HMAC_APPROVED"} for p in pairs]
    edges += [{"from": f"PAIR_{p}", "to": "VAULT", "label": "ATOMIC_COMMIT"} for p in pairs]

    graph_json = json.dumps({"nodes": nodes, "edges": edges})

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <title>ETBV LayerZero STIX 2.1 Command Dashboard</title>
      <meta http-equiv="refresh" content="20">
      <style>
        body {{ background:#0b0f19; color:#e2e8f0; font-family:monospace; padding:20px; margin:0; }}
        h1 {{ color:#38bdf8; margin:0 0 6px 0; font-size:20px; }}
        .badge {{ display:inline-block; background:#064e3b; color:#34d399; padding:4px 10px; border-radius:4px; font-size:12px; margin-bottom:16px; }}
        .panel {{ background:#111827; border:1px solid #1f2937; border-radius:8px; padding:14px; margin-bottom:18px; }}
        .panel-title {{ color:#94a3b8; font-size:12px; text-transform:uppercase; margin-bottom:10px; letter-spacing:1px; }}
        canvas {{ width:100%; height:280px; background:#070a12; border-radius:6px; display:block; cursor:grab; }}
        table {{ width:100%; border-collapse:collapse; }}
        th, td {{ padding:9px 10px; border-bottom:1px solid #1f2937; text-align:left; font-size:13px; }}
        th {{ background:#1e293b; color:#94a3b8; }}
      </style>
    </head>
    <body>
      <h1>ETBV LayerZero Execution & STIX 2.1 Telemetry</h1>
      <div class="badge">GATE: ENFORCED (SINGLE-USE HMAC + 5s TTL) | STIX 2.1 GRAPH LIVE</div>

      <div class="panel">
        <div class="panel-title">Interactive STIX 2.1 Trust Boundary Relationship Graph (Drag Nodes to Inspect)</div>
        <canvas id="stixCanvas"></canvas>
      </div>

      <div class="panel">
        <div class="panel-title">Verified Atomic Executions (Latest 25)</div>
        <table>
          <thead>
            <tr><th>ID</th><th>Pair</th><th>Source</th><th>Target</th><th>Ask</th><th>Bid</th><th>Spread</th></tr>
          </thead>
          <tbody>{table_rows}</tbody>
        </table>
      </div>

      <script>
        const graph = {graph_json};
        const canvas = document.getElementById("stixCanvas");
        const ctx = canvas.getContext("2d");
        canvas.width = canvas.offsetWidth;
        canvas.height = 280;

        const colors = {{ gate: "#38bdf8", source: "#f59e0b", pair: "#a855f7", vault: "#22c55e" }};
        const colX = {{ source: 0.14, gate: 0.42, pair: 0.70, vault: 0.90 }};
        const counts = {{}};

        graph.nodes.forEach(n => {{
          counts[n.group] = (counts[n.group] || 0) + 1;
        }});
        const seen = {{}};
        graph.nodes.forEach(n => {{
          seen[n.group] = (seen[n.group] || 0) + 1;
          n.x = canvas.width * colX[n.group];
          n.y = (canvas.height / (counts[n.group] + 1)) * seen[n.group];
        }});

        let dragging = null;
        canvas.addEventListener("mousedown", e => {{
          const r = canvas.getBoundingClientRect();
          const mx = e.clientX - r.left, my = e.clientY - r.top;
          dragging = graph.nodes.find(n => Math.hypot(n.x - mx, n.y - my) < 22);
        }});
        canvas.addEventListener("mousemove", e => {{
          if (!dragging) return;
          const r = canvas.getBoundingClientRect();
          dragging.x = e.clientX - r.left;
          dragging.y = e.clientY - r.top;
          draw();
        }});
        window.addEventListener("mouseup", () => dragging = null);

        function draw() {{
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          const map = Object.fromEntries(graph.nodes.map(n => [n.id, n]));

          graph.edges.forEach(e => {{
            const a = map[e.from], b = map[e.to];
            if (!a || !b) return;
            ctx.strokeStyle = "#334155";
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();

            const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
            ctx.fillStyle = "#64748b";
            ctx.font = "10px monospace";
            ctx.fillText(e.label, mx - 28, my - 4);
          }});

          graph.nodes.forEach(n => {{
            ctx.fillStyle = colors[n.group] || "#e2e8f0";
            ctx.beginPath();
            ctx.arc(n.x, n.y, 12, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = "#0f172a";
            ctx.lineWidth = 2;
            ctx.stroke();

            ctx.fillStyle = "#f8fafc";
            ctx.font = "11px monospace";
            ctx.fillText(n.label, n.x - 36, n.y + 24);
          }});
        }}
        draw();
      </script>
    </body>
    </html>
    """
