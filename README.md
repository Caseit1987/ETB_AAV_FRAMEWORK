# ETBV Bounded Approval & Ingestion Gate

**Eternal Trust Boundary Validation (ETBV)** is a bounded HTTP approval-and-ingestion architecture that enforces streaming payload size limits, schema/numeric invariants, and single-transaction commit deadlines before writing external records to SQLite.

---

## Core Architecture

* **Streaming Wire Cap & Schema Validation (`app_server.py`):** Reads incoming HTTP request streams chunk-by-chunk, aborting immediately (`HTTP 413`) if cumulative wire bytes exceed `4,096` bytes before full buffering, followed by Pydantic schema and numeric invariant validation.
* **Durable Single-Transaction Nonce & Commit (`BEGIN IMMEDIATE`):**
  * `POST /api/v1/gate/approve` binds a single-use nonce and `HMAC-SHA256` digest to the exact approved payload bytes with a **5-second monotonic deadline** stored in SQLite (`approved_nonces`).
  * `POST /api/v1/ingest/arbitrage` verifies the digest after full stream delivery, checks the monotonic deadline inside a `BEGIN IMMEDIATE` SQLite transaction, atomically deletes the nonce, and inserts the row in one durable transaction.
* **Database-Verified Boundary Tests (`verification/`):**
  * `test_live_gate.py`: Verifies revoked token rejection (`HTTP 403`), `>4,096`-byte stream abort (`HTTP 413`), atomic database commit (`+1` row), post-commit nonce replay rejection (`0` DB change), slow-body deadline expiration (`HTTP 403`, `0` DB change), and `GET /api/v1/audit/snapshot` availability (`HTTP 200`).
  * `trace_verify.py`, `bench_boundary_test.py`, `bench_boundary_hardened.py`: Standalone wire-framing, HAL state-divergence, and HMAC nonce isolation harnesses.
* **Dual-Feed Producers & Keyed Audit Snapshot (`etbv_client.py`):**
  * `scanner_producer.py` & `threat_intel_producer.py`: Automated cross-exchange quote scanner (`BTC/USD`, `ETH/USD`, `SOL/USD`) and deduplicated CISA KEV advisory producer.
  * `export_audit_snapshot.py`: Separates legacy pre-gate rows from cryptographically gated commits, packages STIX 2.1 `observed-data` telemetry, and signs the canonical snapshot using a keyed `HMAC-SHA256` secret (`ETB_AUDIT_SIGNING_KEY`).

---

## Quickstart & Service Management

```bash
chmod +x install.sh
./install.sh
```

```bash
./start_etbv.sh status   # Inspect active PIDs and recent pipeline logs
./start_etbv.sh start    # Restart Gate Server and Dual-Feed Pipeline Daemon
./start_etbv.sh stop     # Stop all background services
```

---

## API Endpoints

| Method | Endpoint | Auth | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/gate/approve` | `X-API-Token` | Enforces 4,096B stream limit and schema invariants; issues a 5s single-use HMAC token + nonce. |
| `POST` | `/api/v1/ingest/arbitrage` | `X-API-Token` + HMAC | Verifies wire digest and deadline inside `BEGIN IMMEDIATE`, burns nonce, and commits row atomically. |
| `GET` | `/api/v1/stix/bundle` | `X-API-Token` | Returns a STIX 2.1 `observed-data` bundle tagging `GATED_HMAC_COMMIT` vs. `LEGACY_PRE_GATE` provenance. |
| `GET` | `/api/v1/audit/snapshot` | `X-API-Token` | Returns the keyed `HMAC-SHA256` signed audit snapshot and boundary proof artifacts. |
| `GET` | `/api/v1/daas/valuations` | `X-API-Token` | Returns raw database rows including `gated_nonce` provenance. |
| `GET` | `/dashboard` | Local | Auto-refreshing HTML ledger displaying provenance status for the latest 25 records. |
