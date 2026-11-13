import hmac
import hashlib
import os
import json
import time

class HardenedProtectedHAL:
    def __init__(self):
        self.main_rail_enabled = False
        self.estop = False
        self.interlock = True
        self._gate_secret = os.urandom(32)  # Ephemeral key private to Layer Zero gate
        self._active_nonces = set()
        self.audit_log = []

    def _log(self, route, action, status, reason):
        self.audit_log.append({
            "timestamp": time.time(),
            "route": route,
            "action": action,
            "status": status,
            "reason": reason,
            "rail_state": self.main_rail_enabled
        })
        print(f"[{status}] Route: {route} | Action: {action} | Reason: {reason} | Rail: {self.main_rail_enabled}")

    def etbv_gate_approve(self, command_bytes):
        if len(command_bytes) != 4 or command_bytes != b"\xaa\xbb\xcc\xdd":
            return None, None, "CAN_FRAME_INVARIANT_VIOLATION"
        if self.estop or not self.interlock:
            return None, None, "SAFETY_INTERLOCK_OPEN"
        nonce = os.urandom(16).hex()
        self._active_nonces.add(nonce)
        msg = command_bytes + f"|{self.estop}|{self.interlock}|{nonce}".encode()
        token = hmac.new(self._gate_secret, msg, hashlib.sha256).hexdigest()
        return token, nonce, "CONTRACT_APPROVED"

    def execute_rail_state(self, route, command_bytes, target_state, token=None, nonce=None):
        if not token or not nonce:
            self._log(route, f"SET_RAIL_{target_state}", "DROP", "MISSING_LAYERZERO_TOKEN")
            return False
        if nonce not in self._active_nonces:
            self._log(route, f"SET_RAIL_{target_state}", "DROP", "REPLAY_OR_INVALID_NONCE")
            return False
        # Burn nonce immediately (single-use atomic enforcement)
        self._active_nonces.remove(nonce)
        expected_msg = command_bytes + f"|{self.estop}|{self.interlock}|{nonce}".encode()
        expected_token = hmac.new(self._gate_secret, expected_msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_token, token):
            self._log(route, f"SET_RAIL_{target_state}", "DROP", "FORGED_TOKEN_OR_TOCTOU_MISMATCH")
            return False
        self.main_rail_enabled = target_state
        self._log(route, f"SET_RAIL_{target_state}", "ALLOW", "VERIFIED_ATOMIC_EXECUTION")
        return True

hal = HardenedProtectedHAL()

# Test 1: Valid single-use execution
tok1, nonce1, _ = hal.etbv_gate_approve(b"\xaa\xbb\xcc\xdd")
hal.execute_rail_state("CAN_BUS_INGRESS", b"\xaa\xbb\xcc\xdd", True, tok1, nonce1)

# Reset rail for replay test
hal.main_rail_enabled = False

# Test 2: Replay attack using previously valid (tok1, nonce1)
hal.execute_rail_state("CAN_BUS_INGRESS", b"\xaa\xbb\xcc\xdd", True, tok1, nonce1)

# Test 3: Forged token attempt without gate secret
fake_nonce = os.urandom(16).hex()
fake_tok = hashlib.sha256(b"\xaa\xbb\xcc\xdd|False|True|" + fake_nonce.encode()).hexdigest()
hal.execute_rail_state("FORGED_CALLER", b"\xaa\xbb\xcc\xdd", True, fake_tok, fake_nonce)

with open("etbv_bench01_hardened_proof.json", "w") as f:
    json.dump(hal.audit_log, f, indent=2)
