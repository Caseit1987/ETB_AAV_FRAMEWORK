import os, json, hmac, hashlib, datetime, urllib.request

BASE_URL = "http://localhost:8000"
PROOF_FILES = [
    "verification/artifacts/etbv_trace_artifact.json",
    "verification/artifacts/etbv_bench01_boundary_proof.json",
    "verification/artifacts/etbv_bench01_hardened_proof.json",
    "verification/artifacts/live_http_gate_proof.json"
]

def generate_audit_snapshot():
    api_token = os.environ["ETB_MASTER_TOKEN"]
    signing_key = os.environ["ETB_AUDIT_SIGNING_KEY"].encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/api/v1/stix/bundle", headers={"X-API-Token": api_token})
    stix_bundle = json.loads(urllib.request.urlopen(req, timeout=5).read().decode("utf-8"))

    obs = next(iter(stix_bundle["objects"]))
    feed = obs["x_etbv_verified_vault_feed"]
    gated_count = sum(1 for r in feed if r.get("provenance") == "GATED_HMAC_COMMIT")
    legacy_count = sum(1 for r in feed if r.get("provenance") == "LEGACY_PRE_GATE")

    proofs = {os.path.basename(p): json.load(open(p)) for p in PROOF_FILES if os.path.exists(p)}
    snapshot = {
        "framework": "ETBV Bounded Approval & Ingestion Prototype",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "provenance_breakdown": {"total_rows": len(feed), "gated_hmac_commit_rows": gated_count, "legacy_pre_gate_rows": legacy_count},
        "boundary_proofs": proofs,
        "stix21_bundle": stix_bundle
    }
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    snapshot["hmac_sha256_signature"] = hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()

    out_path = "verification/artifacts/etbv_full_audit_snapshot.json"
    with open(out_path, "w") as out:
        json.dump(snapshot, out, indent=2)
    print(f"[AUDIT SNAPSHOT] Total: {len(feed)} (Gated: {gated_count}, Legacy: {legacy_count}) | HMAC: {snapshot['hmac_sha256_signature']}", flush=True)

if __name__ == "__main__":
    generate_audit_snapshot()
