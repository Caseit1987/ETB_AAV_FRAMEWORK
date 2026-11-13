# ETBV Bounded Approval & Ingestion Gate - Verification Summary

**Repository:** `Caseit1987/ETB_AAV_FRAMEWORK`  
**Evidence Artifacts:** `verification/artifacts/live_http_gate_proof.json`, `verification/artifacts/etbv_full_audit_snapshot.json`

## Scope
This prototype enforces bounded wire ingestion, single-transaction nonce consumption with a 5.0-second monotonic commit deadline, keyed HMAC-SHA256 audit signing, and SQLite engine-level insert triggers before external records persist to storage.

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
