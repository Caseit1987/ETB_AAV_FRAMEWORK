# ETBV Bounded Approval & Ingestion Gate - Technical Brief

**Repository:** `Caseit1987/ETB_AAV_FRAMEWORK`  
**Architecture Scope:** A bounded HTTP approval-and-ingestion service backed by SQLite that enforces streaming wire limits, single-transaction commit deadlines, keyed HMAC-SHA256 audit signing, and database-level insert triggers before external records persist.

## 1. Enforced System Boundaries
* **Streaming Wire Cap (4,096 Bytes):** Incoming HTTP request streams are read incrementally via chunked streaming and aborted immediately (`HTTP 413`) if cumulative bytes exceed `4,096` bytes prior to full payload buffering.
* **Durable Single-Transaction Nonce & Commit:** Approvals bind a 32-character hex nonce and `HMAC-SHA256` digest to exact wire bytes with a `5.0`-second monotonic deadline. Ingestion verifies the digest, checks the deadline inside a `BEGIN IMMEDIATE` SQLite transaction, deletes the nonce, and inserts the record atomically.
* **Database-Level Write Isolation:** Enforces owner-only file permissions (`chmod 600`) on `monetization_vault.db` and installs a `BEFORE INSERT` SQLite trigger (`trg_require_gated_nonce`) that aborts any direct out-of-band insert lacking a 32-character `gated_nonce`.
* **Keyed Audit Integrity & Provenance:** Audit snapshots separate `LEGACY_PRE_GATE` records from `GATED_HMAC_COMMIT` entries, package STIX 2.1 `observed-data` telemetry, and sign canonical JSON using a keyed `HMAC-SHA256` secret.

## 2. Attributable Verification Evidence

| Test ID | Vector Tested | Enforced Boundary | Verified Outcome |
| :--- | :--- | :--- | :--- |
| **TEST 1** | Legacy hardcoded token | Database key lookup | `HTTP 403` (`DROP: INVALID_API_TOKEN`) |
| **TEST 2** | Payload stream > 4,096 bytes | Chunked stream reader | `HTTP 413` (`DROP: STREAM_EXCEEDED_4096_BYTES`) |
| **TEST 3** | Valid approval + wire-matched ingestion | `BEGIN IMMEDIATE` nonce burn + insert | `HTTP 200` (`0 -> 1` DB row for nonce) |
| **TEST 4** | Post-commit replay of consumed nonce | Atomic nonce deletion | `HTTP 403` (`1` DB row unchanged for nonce) |
| **TEST 5** | Slow-body delivery stalled 5.3s (> 5.0s TTL) | Monotonic deadline check at commit boundary | `HTTP 403` (`0` DB rows for nonce) |
| **TEST 6** | 8-thread concurrent race on identical nonce | SQLite `BEGIN IMMEDIATE` write lock | `1` x `HTTP 200`, `7` x `HTTP 403` (`1` DB row) |
| **TEST 7** | Valid vs. tampered audit snapshot verification | Keyed `HMAC-SHA256` verification endpoint | Valid `HTTP 200`; Tampered `HTTP 403` |
| **TEST 8** | Direct out-of-band SQLite `INSERT` without nonce | SQLite trigger `trg_require_gated_nonce` | Aborted (`DIRECT_UNGATED_INSERT_BLOCKED`) |

## 3. Operational Endpoints

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `POST` | `/api/v1/gate/approve` | Validates stream size and schema invariants; issues 5s single-use HMAC token and nonce. |
| `POST` | `/api/v1/ingest/arbitrage` | Verifies wire digest and deadline inside `BEGIN IMMEDIATE`, burns nonce, and commits row. |
| `GET` | `/api/v1/stix/bundle` | Returns STIX 2.1 `observed-data` bundle tagging `GATED_HMAC_COMMIT` vs. `LEGACY_PRE_GATE` provenance. |
| `GET` | `/api/v1/audit/snapshot` | Returns the keyed `HMAC-SHA256` signed audit snapshot and boundary proof artifacts. |
| `POST` | `/api/v1/audit/verify` | Recomputes canonical `HMAC-SHA256` to verify any exported audit snapshot. |

## 4. Explicit Trust Boundary & Scope
* **Trusted Same-UID Host:** Same-UID processes share filesystem access to `monetization_vault.db` and `.env` and are explicitly within the trusted computing base.
* **Scope of SQLite Guardrails:** `trg_require_gated_nonce` enforces schema provenance against accidental out-of-band writes; enforcing adversarial isolation against local processes requires running the database under a separate OS user or remote service boundary.
