#!/usr/bin/env python3
import sys
import json

# Simulated state (in a real system, persist across calls)
# Persistent state handling
STATE_FILE = "aav_balances.json"
DEFAULT_BALANCES = {"alice": 1000, "bob": 500}

def load_balances():
    import os, json
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f: json.dump(DEFAULT_BALANCES, f)
        return DEFAULT_BALANCES
    with open(STATE_FILE, "r") as f: return json.load(f)

def save_balances(balances):
    import json
    with open(STATE_FILE, "w") as f: json.dump(balances, f)

BALANCES = load_balances()
VALID_TOKENS = {"token123": "alice", "token456": "bob"}

def authenticate(token):
    return VALID_TOKENS.get(token)

def authorize(user, action, resource):
    # Simple example: only alice can withdraw more than 100
    if action == "withdraw" and resource == "bank":
        return user == "alice"  # Bob cannot withdraw
    return True

def validate(action, amount, user):
    if action == "withdraw":
        balance = BALANCES.get(user, 0)
        if amount > balance:
            return False, f"Insufficient balance ({balance} < {amount})"
        # Also block the 46D1 key if it appears in the request string
        # (this is just for demonstration; you already have that in Rust)
    return True, "OK"

def main():
    if len(sys.argv) != 2:
        print("Usage: aav_check.py <request_json>", file=sys.stderr)
        sys.exit(1)
    try:
        req = json.loads(sys.argv[1])
    except:
        print("ERROR: invalid JSON", file=sys.stderr)
        sys.exit(1)

    token = req.get("token", "")
    user = authenticate(token)
    if not user:
        print("BLOCKED: Authentication failed")
        sys.exit(1)

    action = req.get("action")
    resource = req.get("resource")
    if not authorize(user, action, resource):
        print("BLOCKED: Authorization failed")
        sys.exit(1)

    amount = req.get("amount", 0)
    valid, msg = validate(action, amount, user)
    if not valid:
        print(f"BLOCKED: {msg}")
        sys.exit(1)

    # Optionally update state (e.g., deduct balance)
    if action == "withdraw":
        BALANCES[user] -= amount

    save_balances(BALANCES)
    print("ALLOWED")
    sys.exit(0)

if __name__ == "__main__":
    main()
