import struct
from protocol_parser import parse_layerzero_packet
from state_engine import TrustBoundaryState
from crypto_verify import verify_payload_authenticity
import hmac
import hashlib

def run_diagnostic_suite():
    print("[+] Running Diagnostics...")
    state_manager = TrustBoundaryState()
    secret_key = b"ETB_SYSTEM_PERIMETER_SECRET_KEY_2026"

    mock_payload = b"Omnichain_Asset_Transfer_Data"
    payload_length = len(mock_payload)
    header = struct.pack(">QIII", 1, 101, 202, payload_length)
    valid_packet = header + mock_payload

    valid_sig = hmac.new(secret_key, mock_payload, hashlib.sha256).hexdigest()

    print("Processing Valid Structural Frame...")
    parsed = parse_layerzero_packet(valid_packet)
    if parsed["valid"]:
        n_ok, n_msg = state_manager.validate_and_update_nonce(parsed["src_chain"], parsed["nonce"])
        c_ok = verify_payload_authenticity(parsed["payload"], valid_sig)
        print(f"    -> Parsing: SUCCESS (Nonce: {parsed['nonce']}, Src: {parsed['src_chain']}, Dst: {parsed['dst_chain']})")
        print(f"    -> Sequence: {n_msg}")
        print(f"    -> Cryptographic: {'SUCCESS' if c_ok else 'FAILED'}")
    else:
        print(f"    -> Failed: {parsed['reason']}")

    print("\nSimulating Replay Attack Vector...")
    replay_ok, replay_msg = state_manager.validate_and_update_nonce(101, 1)
    print(f"    -> Response: {'PASSED' if replay_ok else 'BLOCKED - ' + replay_msg}")

    print("\nSimulating Cryptographic Signature Evasion...")
    c_ok_evasion = verify_payload_authenticity(mock_payload, "malicious_forged_string")
    print(f"    -> Response: {'PASSED' if c_ok_evasion else 'BLOCKED - Constant-Time HMAC Rejection'}")

if __name__ == "__main__":
    run_diagnostic_suite()
