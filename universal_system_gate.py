import json
import sys

# Pre-defined strict system schema boundaries
MAX_COMMAND_LENGTH = 50
ALLOWED_SYSTEM_CHARACTERS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_- ")

def universal_ingress_validator(raw_request_json):
    try:
        req = json.loads(raw_request_json)
    except:
        return False, "ERR_STRUCTURAL_MALFORMED_JSON"

    command = req.get("command", "")
    system_target = req.get("target_subsystem", "")

    # Rule 1: Static Size Constraint Check (O(1))
    if len(command) > MAX_COMMAND_LENGTH:
        return False, "ERR_OVERSIZED_PAYLOAD_REJECTED"

    # Rule 2: Zero-Copy Semantic Character Sanitization 
    # Instantly drops shell injection attempts (; , &&, ||, ../) at ingress
    if not all(char in ALLOWED_SYSTEM_CHARACTERS for char in command):
        return False, "ERR_MALICIOUS_CHARACTER_INJECTION_DETECTED"

    # Rule 3: Linear State Authorization Boundary
    if system_target == "kernel_core" and command != "sysctl -a":
        return False, "ERR_UNAUTHORIZED_SUBSYSTEM_TRAVERSAL"

    return True, f"EXECUTE_SAFE: {command}"

if __name__ == "__main__":
    # Test Vector 1: Standard legitimate cloud server telemetry call
    print("--- Test 1: Valid Linux Server Command ---")
    ok, msg = universal_ingress_validator('{"target_subsystem": "telemetry", "command": "uptime"}')
    print(f"Result: {'ALLOWED' if ok else 'BLOCKED'} | Detail: {msg}\n")

    # Test Vector 2: High-Severity OS Shell Injection Attack (RCE Attempt)
    print("--- Test 2: OS Shell Injection Attack ---")
    ok, msg = universal_ingress_validator('{"target_subsystem": "telemetry", "command": "uptime; rm -rf /"}')
    print(f"Result: {'ALLOWED' if ok else 'BLOCKED'} | Detail: {msg}\n")

    # Test Vector 3: Unauthorized Subsystem Traversal Attack
    print("--- Test 3: Unauthorized Subsystem Traversal ---")
    ok, msg = universal_ingress_validator('{"target_subsystem": "kernel_core", "command": "format c:"}')
    print(f"Result: {'ALLOWED' if ok else 'BLOCKED'} | Detail: {msg}")
