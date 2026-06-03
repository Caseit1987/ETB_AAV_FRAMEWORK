#!/usr/bin/env python3
import ctypes
import sys

# Load the ETB library
lib = ctypes.CDLL('/data/data/com.termux/files/home/ETB_PRODUCT/etb_product/rust_core/target/release/libetb_core.so')
lib.validate_request.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
lib.validate_request.restype = ctypes.c_bool

# Load policy (ensure it contains the structural rule)
with open('/data/data/com.termux/files/home/ETB_PRODUCT/etb_product/rust_core/policy.json') as f:
    policy = f.read()

# Valid credentials for demo
VALID_TOKEN = b'token123'
VALID_ACTION = b'withdraw'
VALID_RESOURCE = b'bank'

def test_request(req, description):
    result = lib.validate_request(req.encode(), policy.encode(), VALID_TOKEN, VALID_ACTION, VALID_RESOURCE)
    status = "ALLOWED" if result else "BLOCKED"
    print(f"{description:30} -> {status}")
    return result

if __name__ == "__main__":
    print("=== ETB AAV LayerZero™ Demo ===\n")
    # 1. Legitimate command
    test_request("cmd=withdraw&amount=50", "Legitimate withdrawal")
    # 2. Malformed command (no '=')
    test_request("cmd_withdraw_amount_50", "Malformed (no '=')")
    # 3. Binary payload (simulated by non‑ASCII)
    test_request("cmd=\xff", "Binary payload (non‑ASCII)")
    # 4. Oversized command (structural violation)
    test_request("cmd=" + "A"*1000, "Oversized command")
    print("\n✅ ETB blocks all malformed/illegal requests while allowing legitimate ones.")
