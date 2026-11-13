# ETBV Bounded Approval & Ingestion Gate

**Eternal Trust Boundary Validation (ETBV)** is a bounded HTTP approval-and-ingestion architecture that enforces streaming payload size limits, schema/numeric invariants, and single-transaction commit deadlines before writing external records to SQLite.

---

## Core Architecture

* **Streaming Wire Cap & Schema Validation (`app_server.py`):** Reads incoming HTTP request streams chunk-by-chunk, aborting immediately (`HTTP 413`) if cumulative wire bytes exceed `4,096` bytes before full buffering, followed by Pydantic schema and numeric invariant validation.
* **Durable Single-Transaction Nonce & Commit (`BEGIN IMMEDIATE`):**
  * `POST /api/v1/gate/approve` binds a single-use nonce and `HMAC-SHA256` digest to the exact approved payload bytes with a **5-second monotonic deadline** stored in SQLite (`approved_nonces`).
  * `POST /api/v1/ingest/arbitrage` verifies the digest after full stream delivery, checks the monotonic deadline inside a `BEGIN IMMEDIATE` SQLite transaction, atomically deletes the nonce, and inserts the row in one durable transaction.
* **Database-Verified Boundary & Concurrency Suite (`verification/test_live_gate.py`):**
  * **Credential Revocation (`TEST 1`):** Verifies legacy hardcoded tokens return `HTTP 403`.
  * **Chunked Streaming Byte Cap (`TEST 2`):** Verifies `>4,096`-byte streams abort with `HTTP 413` prior to buffering.
  * **Atomic Single-Transaction Commit (`TEST 3`):** Verifies valid approval commits cleanly (`HTTP 200`, `+1` SQLite row).
  * **Post-Commit Nonce Replay (`TEST 4`):** Verifies replay of a nonce consumed by a successful commit returns `HTTP 403` with `0` SQLite row change.
  * **Slow-Body Commit Deadline (`TEST 6`):** Verifies slow body delivery past the 5-second deadline fails at the commit boundary (`HTTP 403`, `0` SQLite row change).
  * **8-Thread Concurrent Race Condition (`TEST 7`):** Fires 8 parallel requests with the same approved nonce; `BEGIN IMMEDIATE` serializes execution so `1` succeeds (`HTTP 200`, `+1` row) and `7` fail (`HTTP 403`).
  * **Keyed HMAC Signature Verification (`TEST 8`):** Verifies valid audit packages return `HTTP 200` (`SIGNATURE_VERIFIED`) while tampered payloads fail with `HTTP 403` (`DROP: AUDIT_HMAC_SIGNATURE_MISMATCH`).
* **Dual-Feed Producers & Keyed Audit Snapshot (`etbv_client.py`):**
  * `scanner_producer.py` & `threat_intel_producer.py`: Automated cross-exchange quote scanner (`BTC/USD`, `ETH/USD`, `SOL/USD`) and deduplicated CISA KEV advisory producer.
  * `export_audit_snapshot.py`: Separates legacy pre-gate rows (`LEGACY_PRE_GATE`) from cryptographically bound commits (`GATED_HMAC_COMMIT`), packages STIX 2.1 `observed-data` telemetry, and signs the canonical snapshot using a keyed `HMAC-SHA256` secret (`ETB_AUDIT_SIGNING_KEY`).

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
| `POST` | `/api/v1/audit/verify` | `X-API-Token` | Recomputes canonical `HMAC-SHA256` against `ETB_AUDIT_SIGNING_KEY` to verify any exported snapshot. |
| `GET` | `/api/v1/daas/valuations` | `X-API-Token` | Returns raw database rows including `gated_nonce` provenance. |
| `GET` | `/dashboard` | Local | Auto-refreshing HTML ledger displaying provenance status for the latest 25 records. |
