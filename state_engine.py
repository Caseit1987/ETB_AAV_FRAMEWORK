class TrustBoundaryState:
    def __init__(self):
        # Dictionary mapping chain_id -> last_seen_nonce
        self.chain_nonces = {}

    def validate_and_update_nonce(self, chain_id, incoming_nonce):
        """
        Enforces strict chronological sequence ordering.
        An incoming nonce must be exactly last_seen_nonce + 1.
        """
        last_nonce = self.chain_nonces.get(chain_id, 0)
        
        if incoming_nonce <= last_nonce:
            return False, f"REPLAY_ATTACK_DETECTED: Nonce {incoming_nonce} is stale. Last was {last_nonce}."
            
        if incoming_nonce != last_nonce + 1:
            return False, f"SEQUENCE_GAP_DETECTED: Expected {last_nonce + 1}, got {incoming_nonce}."
            
        # Update internal state securely
        self.chain_nonces[chain_id] = incoming_nonce
        return True, "SUCCESS"
