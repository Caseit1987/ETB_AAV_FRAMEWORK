import os
import json
import hashlib
import datetime
from n8n_telemetry_bridge import fetch_verified_vault_rows, build_stix_bundle

PROOF_FILES = [
    "verification/artifacts/etbv_trace_artifact.json",
    "verification/artifacts/etbv_bench01_boundary_proof.json",
    "verification/artifacts/etbv_bench01_hardened_proof.json",
    "verification/artifacts/live_http_gate_proof.json"
]

def generate_audit_snapshot():
    token = os.environ["ETB_MASTER_TOKEN"]
    rows = fetch_verified_vault_rows(token)
    stix_bundle = build_stix_bundle(rows)

    proofs = {}
    for path in PROOF_FILES:
        if os.path.exists(path):
            with open(path, "r") as f:
                proofs[os.path.basename(path)] = json.load(f)

    snapshot = {
        "framework": "ETBV AAV LayerZero Framework",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "gate_invariants": [
            "PRE_PARSER_WIRE_CONTRACT_VALIDATION",
            "GATE_PRIVATE_HMAC_SHA256_BINDING",
            "SINGLE_USE_MONOTONIC_NONCE_5S_TTL",
            "FAIL_CLOSED_EXECUTION_BOUNDARY"
        ],
        "non_bypassability_proofs": proofs,
        "live_stix21_telemetry_bundle": stix_bundle
    }

    serialized = json.dumps(snapshot, indent=2)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    snapshot["snapshot_sha256"] = digest

    out_path = "verification/artifacts/etbv_full_audit_snapshot.json"
    with open(out_path, "w") as out:
        json.dump(snapshot, out, indent=2)

    print(f"[AUDIT SNAPSHOT] Exported {len(rows)} verified vault rows + {len(proofs)} boundary proofs -> {out_path}")
    print(f"[AUDIT SNAPSHOT] Integrity SHA-256: {digest}")

if __name__ == "__main__":
    generate_audit_snapshot()
