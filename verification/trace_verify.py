import socket
import struct
import threading
import time
import json

# Simulated Protected State (Target Controller Register)
PROTECTED_REGISTER = {"address": 0x0010, "value": 0x0000}
TELEMETRY_LOG = []

def log_event(route, status, raw_bytes, reason):
    entry = {
        "timestamp": time.time(),
        "route": route,
        "decision": status,
        "payload_hex": raw_bytes.hex(),
        "reason": reason
    }
    TELEMETRY_LOG.append(entry)
    print(f"[{status}] Route: {route} | Reason: {reason} | Hex: {raw_bytes.hex()}")

# Downstream Target Execution (Simulates physical/memory effect)
def execute_target_write(func_code, reg_addr, reg_val):
    if func_code == 0x06 and reg_addr == PROTECTED_REGISTER["address"]:
        PROTECTED_REGISTER["value"] = reg_val

# ETBV Layer Zero Pre-Parser Gate
def etbv_gate_inspect(data):
    # Fail-closed on empty or truncated Modbus TCP MBAP header (< 8 bytes)
    if len(data) < 8:
        return False, "FAIL_CLOSED_TRUNCATED_HEADER"
    
    # Unpack MBAP Header: Transaction ID (2), Protocol ID (2), Length (2), Unit ID (1), Function Code (1)
    tx_id, proto_id, declared_len, unit_id, func_code = struct.unpack(">HHHBB", data[:8])
    
    # Check 1: Strict Protocol ID == 0x0000
    if proto_id != 0x0000:
        return False, "INVALID_PROTOCOL_ID"
    
    # Check 2: Byte Aliasing / Trailing Smuggling Check (Declared length must match exact wire bytes)
    actual_payload_len = len(data) - 6
    if declared_len != actual_payload_len:
        return False, f"BYTE_ALIASING_MISMATCH (Declared:{declared_len} != Actual:{actual_payload_len})"
    
    # Check 3: Scoped Write Contract (Only allow writing 0x0001 to 0x0010)
    if func_code == 0x06:
        if len(data) != 12:
            return False, "MALFORMED_WRITE_LENGTH"
        reg_addr, reg_val = struct.unpack(">HH", data[8:12])
        if reg_addr == 0x0010 and reg_val != 0x0001:
            return False, f"UNAUTHORIZED_REGISTER_VALUE ({hex(reg_val)})"
            
    return True, "CONTRACT_APPROVED"

# Gate Listener (Port 15020 -> forwards only approved frames to internal target)
def start_etbv_gate():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("localhost", 15020))
    srv.listen(5)
    while True:
        conn, _ = srv.accept()
        data = conn.recv(1024)
        if data:
            approved, reason = etbv_gate_inspect(data)
            if approved:
                log_event("PRIMARY_ETBV_GATE", "ALLOW", data, reason)
                _, _, _, _, func_code = struct.unpack(">HHHBB", data[:8])
                reg_addr, reg_val = struct.unpack(">HH", data[8:12])
                execute_target_write(func_code, reg_addr, reg_val)
                conn.sendall(b"ACK")
            else:
                log_event("PRIMARY_ETBV_GATE", "DROP", data, reason)
                conn.close() # Immediate RST/DROP
        conn.close()

# Run Trace Tests
def run_verification_suite():
    threading.Thread(target=start_etbv_gate, daemon=True).start()
    time.sleep(0.3)

    print("=== STARTING ETBV OPERATION TRACE ===\n")

    # TRACE 1: Valid Contract Write (0x06 Write 0x0001 to Register 0x0010)
    valid_frame = struct.pack(">HHHBBHH", 1, 0, 6, 1, 0x06, 0x0010, 0x0001)
    with socket.create_connection(("localhost", 15020)) as s:
        s.sendall(valid_frame)
    time.sleep(0.1)
    print(f"Target State after Trace 1: {PROTECTED_REGISTER}\n")

    # TRACE 2: Byte Aliasing / Smuggled Frame (Header declares length 6, appends unauthorized write to 0xDEAD)
    smuggled_frame = struct.pack(">HHHBBHH", 2, 0, 6, 1, 0x06, 0x0010, 0x0001) + b"\x00\x06\x00\x10\xDE\xAD"
    with socket.create_connection(("localhost", 15020)) as s:
        s.sendall(smuggled_frame)
    time.sleep(0.1)
    print(f"Target State after Trace 2: {PROTECTED_REGISTER}\n")

    # TRACE 3: Unauthorized Value Mutation (Valid framing, invalid register value 0x9999)
    bad_val_frame = struct.pack(">HHHBBHH", 3, 0, 6, 1, 0x06, 0x0010, 0x9999)
    with socket.create_connection(("localhost", 15020)) as s:
        s.sendall(bad_val_frame)
    time.sleep(0.1)
    print(f"Target State after Trace 3: {PROTECTED_REGISTER}\n")

    with open("etbv_trace_artifact.json", "w") as f:
        json.dump({"final_state": PROTECTED_REGISTER, "telemetry": TELEMETRY_LOG}, f, indent=2)
    print("=== TRACE COMPLETE: Artifact saved to etbv_trace_artifact.json ===")

if __name__ == "__main__":
    run_verification_suite()
