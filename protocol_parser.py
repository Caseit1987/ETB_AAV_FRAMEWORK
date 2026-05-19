import struct

def parse_layerzero_packet(raw_data):
    if len(raw_data) < 20:
        return {"valid": False, "reason": "MALFORMED_HEADER_TOO_SHORT"}

    try:
        nonce, src_chain, dst_chain, payload_len = struct.unpack(">QIII", raw_data[:20])
        actual_payload = raw_data[20:]
        if len(actual_payload) != payload_len:
            return {"valid": False, "reason": "PAYLOAD_LENGTH_MISMATCH"}

        return {
            "valid": True,
            "nonce": nonce,
            "src_chain": src_chain,
            "dst_chain": dst_chain,
            "payload": actual_payload
        }
    except Exception as e:
        return {"valid": False, "reason": f"PARSING_EXCEPTION: {str(e)}"}
