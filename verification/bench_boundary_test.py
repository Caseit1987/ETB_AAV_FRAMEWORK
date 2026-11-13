import hashlib
import json
import time

class ProtectedHAL:
    def __init__(self):
        self.main_rail_enabled = False
        self.estop = False
        self.interlock = True
        self.audit_log = []

    def _log(self, route, action, status, reason):
        entry = {
            "timestamp": time.time(),
            "route": route,
            "action": action,
            "status": status,
            "reason": reason,
            "rail_state": self.main_rail_enabled
        }
        self.audit_log.append(entry)
        print(f"[{status}] Route: {route} | Action: {action} | Reason: {reason} | Rail: {self.main_rail_enabled}")

    def etbv_gate_approve(self, command_bytes, estop_snapshot, interlock_snapshot):
        # Invariant 1: Exact 4-byte command frame (no trailing CAN byte aliasing)
        if len(command_bytes) != 4 or command_bytes != b"\xaa\xbb\xcc\xdd":
            return None, "CAN_FRAME_INVARIANT_VIOLATION"
        # Invariant 2: Safety continuity check
        if estop_snapshot or not interlock_snapshot:
            return None, "SAFETY_INTERLOCK_OPEN"
        # Bind approval to exact command + safety state snapshot
        state_blob = command_bytes + f"|{estop_snapshot}|{interlock_snapshot}".encode()
        return hashlib.sha256(state_blob).hexdigest(), "CONTRACT_APPROVED"

    def enable_main_rail(self, route, command_bytes, approval_token=None):
        if not approval_token:
            self._log(route, "ENABLE_RAIL", "DROP", "MISSING_LAYERZERO_TOKEN")
            return False
        # Re-verify current live hardware state against bound approval token (TOCTOU guard)
        live_blob = command_bytes + f"|{self.estop}|{self.interlock}".encode()
        if hashlib.sha256(live_blob).hexdigest() != approval_token:
            self._log(route, "ENABLE_RAIL", "DROP", "TOCTOU_STATE_DIVERGENCE")
            return False
        self.main_rail_enabled = True
        self._log(route, "ENABLE_RAIL", "ALLOW", "VERIFIED_EXECUTION")
        return True

hal = ProtectedHAL()

# Test A: Direct HAL call bypassing gate
hal.enable_main_rail("DIRECT_INTERNAL_CALL", b"\xaa\xbb\xcc\xdd", approval_token=None)

# Test B: Smuggled CAN payload (TC-05 vector)
token_b, reason_b = hal.etbv_gate_approve(b"\xaa\xbb\xcc\xdd\xff\x01", hal.estop, hal.interlock)
if not token_b:
    hal._log("CAN_BUS_INGRESS", "ENABLE_RAIL", "DROP", reason_b)

# Test C: TOCTOU E-Stop trip after gate approval (TC-01 vector)
token_c, _ = hal.etbv_gate_approve(b"\xaa\xbb\xcc\xdd", hal.estop, hal.interlock)
hal.estop = True  # E-Stop triggered mid-flight before HAL execution
hal.enable_main_rail("CAN_BUS_INGRESS", b"\xaa\xbb\xcc\xdd", approval_token=token_c)

# Test D: Valid nominal execution (Reset E-Stop)
hal.estop = False
token_d, _ = hal.etbv_gate_approve(b"\xaa\xbb\xcc\xdd", hal.estop, hal.interlock)
hal.enable_main_rail("CAN_BUS_INGRESS", b"\xaa\xbb\xcc\xdd", approval_token=token_d)

with open("etbv_bench01_boundary_proof.json", "w") as f:
    json.dump(hal.audit_log, f, indent=2)
