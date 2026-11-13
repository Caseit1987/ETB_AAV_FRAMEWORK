# ETBV Bounded Approval & Ingestion Gate - Verification Summary

**Repository:** `Caseit1987/ETB_AAV_FRAMEWORK`  
**Evidence Artifacts:** `verification/artifacts/live_http_gate_proof.json`, `verification/artifacts/etbv_full_audit_snapshot.json`

## Scope & Explicit Boundaries
* **Enforced Scope:** Bounded HTTP wire ingestion (`4,096B` stream cap), single-transaction nonce consumption with a `5.0s` monotonic commit deadline (`BEGIN IMMEDIATE` + `PRAGMA synchronous = FULL`), keyed `HMAC-SHA256` audit signing, and live SQLite backup recovery.
* **Explicit Remaining Boundaries:**
  1. **Trusted Same-UID Host:** Same-UID processes share filesystem access to SQLite and `.env`; `trg_require_gated_nonce` checks 32-character nonce length as an accidental-bypass guardrail rather than adversarial isolation against a same-UID process.
  2. **Ephemeral Gate Secret on Restart:** `GATE_SECRET` is generated per process boot; any unconsumed approval nonces issued before a crash/restart fail closed and must be re-approved by the recovered instance.
  3. **Backup Cadence:** Hourly execution (`ETBV_BACKUP_SECONDS=3600`) is configured in `pipeline_daemon.py` and verified at daemon startup; retention eviction order (`TEST 9A`) and live service recovery (`TEST 9B`) are verified deterministically in the test suite.

## Verified Invariants (`verification/test_live_gate.py`)

| Test | Vector Tested | Enforced Boundary | Verified Outcome |
| :--- | :--- | :--- | :--- |
| `TEST 1` | Legacy hardcoded token (`ETB_SECURE_TOKEN_99X`) | Database key lookup (`verify_db_token`) | `HTTP 403` (`DROP: INVALID_API_TOKEN`) |
| `TEST 2` | Payload stream `> 4,096` bytes | Chunked stream reader (`read_bounded_stream`) | `HTTP 413` (`DROP: STREAM_EXCEEDED_4096_BYTES`) |
| `TEST 3` | Valid approval + wire-matched ingestion | `BEGIN IMMEDIATE` nonce burn + insert | `HTTP 200` (`0 -> 1` DB row for nonce) |
| `TEST 4` | Post-commit replay of consumed nonce | Atomic nonce deletion in `approved_nonces` | `HTTP 403` (`1` DB row unchanged for nonce) |
| `TEST 5` | Slow-body delivery stalled `5.3s` (`> 5.0s` TTL) | Monotonic deadline check at commit boundary | `HTTP 403` (`0` DB rows for nonce) |
| `TEST 6` | 8-thread concurrent race on identical nonce | SQLite `BEGIN IMMEDIATE` write lock | `1` x `HTTP 200`, `7` x `HTTP 403` (`1` DB row) |
| `TEST 7` | Valid vs. tampered audit snapshot verification | Keyed `HMAC-SHA256` (`POST /api/v1/audit/verify`) | Valid `HTTP 200`; Tampered `HTTP 403` |
| `TEST 8` | Direct out-of-band SQLite `INSERT` without nonce | SQLite trigger `trg_require_gated_nonce` | Aborted (`DIRECT_UNGATED_INSERT_BLOCKED`) |
| `TEST 9A` | 8-file rotation retention eviction order | Oldest-mtime eviction (`backup_vault.sh`) | Oldest file evicted; `7` newest retained |
| `TEST 9B` | Live service boot (`:8001`) from restored backup | Full FastAPI + SQLite + key + gate recovery | `100%` row-for-row match + `HTTP 200` commit |
