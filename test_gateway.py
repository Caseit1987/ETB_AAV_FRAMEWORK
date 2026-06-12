#!/usr/bin/env python3
import subprocess
import json
import random
import sys

VALID_TOKENS = ["token123", "token456"]
VALID_USERS = {"token123": "alice", "token456": "bob"}
BALANCES = {"alice": 1000, "bob": 500}

def generate_valid():
    token = random.choice(VALID_TOKENS)
    user = VALID_USERS[token]
    if random.choice([True, False]):
        action = "withdraw"
        amount = random.randint(1, BALANCES[user])
        resource = "bank"
    else:
        action = "check"
        amount = 0
        resource = "bank"
    return {"token": token, "action": action, "resource": resource, "amount": amount}

def generate_invalid():
    # Bad token, overdraft, wrong resource, etc.
    case = random.choice(["bad_token", "overdraft", "unauthorized_action", "malformed"])
    if case == "bad_token":
        return {"token": "fake_token", "action": "withdraw", "resource": "bank", "amount": 10}
    elif case == "overdraft":
        token = random.choice(VALID_TOKENS)
        user = VALID_USERS[token]
        # amount > balance
        amount = BALANCES[user] + random.randint(1, 500)
        return {"token": token, "action": "withdraw", "resource": "bank", "amount": amount}
    elif case == "unauthorized_action":
        token = "token456"  # bob
        return {"token": token, "action": "withdraw", "resource": "bank", "amount": 50}
    else:  # malformed JSON or missing fields
        return {"token": VALID_TOKENS[0]}  # missing action/resource/amount

def run_test(request):
    req_json = json.dumps(request)
    try:
        result = subprocess.run(
            ["python3", "aav_check.py", req_json],
            capture_output=True,
            text=True,
            timeout=2
        )
        output = result.stdout.strip()
        if "ALLOWED" in output:
            return "ALLOWED"
        elif "BLOCKED" in output:
            return "BLOCKED"
        else:
            return "ERROR"
    except:
        return "TIMEOUT"

def main():
    total = 1000
    valid_count = 0
    invalid_count = 0
    allowed_valid = 0
    blocked_valid = 0
    allowed_invalid = 0
    blocked_invalid = 0

    for i in range(total):
        # 30% valid, 70% invalid (similar to earlier fuzzer)
        if random.random() < 0.3:
            req = generate_valid()
            valid_count += 1
            expected = "ALLOWED"
        else:
            req = generate_invalid()
            invalid_count += 1
            expected = "BLOCKED"
        result = run_test(req)
        if expected == "ALLOWED":
            if result == "ALLOWED":
                allowed_valid += 1
            else:
                blocked_valid += 1
        else:  # expected BLOCKED
            if result == "BLOCKED":
                blocked_invalid += 1
            else:
                allowed_invalid += 1

    total_events = total
    total_blocked = blocked_valid + blocked_invalid
    neutralization = total_blocked / total_events * 100

    print(f"=== Gateway Test Results ===")
    print(f"Total requests: {total_events}")
    print(f"Valid requests (should be allowed): {valid_count}")
    print(f"Invalid requests (should be blocked): {invalid_count}")
    print(f"Allowed valid (true negatives? no – true positives for allow): {allowed_valid}")
    print(f"Blocked valid (false positives): {blocked_valid}")
    print(f"Allowed invalid (false negatives, attacks got through): {allowed_invalid}")
    print(f"Blocked invalid (true positives): {blocked_invalid}")
    print(f"Neutralization rate (blocked/all): {neutralization:.2f}%")
    print(f"Attack detection rate (blocked_invalid / invalid): {blocked_invalid/invalid_count*100:.2f}%")
    print(f"False positive rate (blocked_valid / valid): {blocked_valid/valid_count*100:.2f}%")

if __name__ == "__main__":
    main()
