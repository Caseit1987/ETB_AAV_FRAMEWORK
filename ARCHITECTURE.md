# ETB Engineering Architecture Specifications

## Core Components

1. **Protocol Extraction (`protocol_parser.py`)**
   * Decodes incoming binary stream segments using fixed byte widths (`struct.unpack`).
   * Verifies header dimensions against payload offsets to catch truncation.

2. **Sequence Tracking State Engine (`state_engine.py`)**
   * Maps source chains to incremental integers.
   * Drops non-sequential or duplicate identifiers to prevent transactional replaying.

3. **Cryptographic Validation (`crypto_verify.py`)**
   * Performs constant-time data matching via `hmac.compare_digest`.
   * Isolates validation execution times to mitigate side-channel leaks.
