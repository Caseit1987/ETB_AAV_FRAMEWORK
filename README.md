# ETBV AAV LayerZero Framework

**Eternal Trust Boundary Validation (ETBV)** is a deterministic, pre-parser Layer Zero execution gate designed to enforce non-bypassable contract invariants before untrusted wire bytes reach downstream parsers, hardware abstraction layers, or database vaults.

---

## Core Architecture

* **Layer Zero Pre-Parser Gate (`app_server.py`):** Evaluates raw byte frames against structural and domain invariants prior to execution, binding approvals to a gate-private `HMAC-SHA256` secret and a single-use monotonic nonce with a strict **5-second TTL**.
* **Non-Bypassability Verification Suite (`verification/`):**
  * `trace_verify.py`: Wire-level byte aliasing and trailing payload smuggling verification.
  * `bench_boundary_test.py`: Direct Hardware Abstraction Layer (HAL) call isolation and mid-flight `E-Stop` TOCTOU state-divergence verification.
  * `bench_boundary_hardened.py`: Single-use monotonic nonce replay resistance and gate-private HMAC forgery rejection.
  * `test_live_gate.py`: Live HTTP boundary verification against `localhost:8000`.
* **Dual-Feed Producers (`etbv_client.py`):**
  * `scanner_producer.py`: Real-time cross-exchange spot spread scanner (`BTC/USD`, `ETH/USD`, `SOL/USD`) enforcing raw wire-byte signing.
  * `threat_intel_producer.py`: Live CISA Known Exploited Vulnerabilities (KEV) advisory feed routed through the identical Layer Zero HMAC gate.
* **STIX 2.1 Telemetry & Interactive Command Dashboard:**
  * `GET /api/v1/stix/bundle`: Live STIX 2.1 `observed-data` bundle endpoint.
  * `GET /dashboard`: Self-contained interactive HTML5 Canvas STIX 2.1 relationship graph and live execution ledger.
  * `n8n_telemetry_bridge.py`: Automated STIX 2.1 webhook dispatcher with local snapshot fallback.

---

## Quickstart Deployment

```bash
chmod +x install.sh
./install.sh
```

### Daemon Management
```bash
./start_etbv.sh status   # Inspect active PIDs and recent telemetry logs
./start_etbv.sh start    # Restart LayerZero Gate and Dual-Feed Pipeline Daemon
./start_etbv.sh stop     # Stop all background services
```

---

## API Endpoints

| Method | Endpoint | Auth | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/gate/approve` | `X-API-Token` | Validates raw wire bytes against pre-parser invariants and issues a 5s single-use HMAC token + nonce. |
| `POST` | `/api/v1/ingest/arbitrage` | `X-API-Token` + HMAC | Burns nonce atomically, verifies raw wire digest, and commits state to SQLite. |
| `GET` | `/api/v1/stix/bundle` | `X-API-Token` | Returns a live STIX 2.1 `observed-data` bundle of all verified vault records. |
| `GET` | `/api/v1/daas/valuations` | `X-API-Token` | Returns raw verified vault rows. |
| `GET` | `/dashboard` | Local | Interactive STIX 2.1 trust-boundary relationship graph and live execution table. |
