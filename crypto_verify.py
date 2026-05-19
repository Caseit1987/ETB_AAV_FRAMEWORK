import hmac
import hashlib

# In production, this secret key is securely stored in an environment variable or hardware enclave
SHARED_SECRET_KEY = b"ETB_SYSTEM_PERIMETER_SECRET_KEY_2026"

def verify_payload_authenticity(payload, incoming_signature):
    """
    Computes a localized cryptographic signature of the payload
    and performs a constant-time comparison to eliminate timing attacks.
    """
    expected_signature = hmac.new(SHARED_SECRET_KEY, payload, hashlib.sha256).hexdigest()
    
    # hmac.compare_digest eliminates side-channel timing vulnerabilities
    return hmac.compare_digest(expected_signature.encode(), incoming_signature.encode())
