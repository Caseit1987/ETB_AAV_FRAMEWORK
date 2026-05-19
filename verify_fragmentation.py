import socket
import struct
import time

def run_fragmentation_test():
    print("[+] Initializing Structural Fragmentation Evaluation...")
    
    # 1. Construct a valid big-endian 20-Byte Header + Payload
    # Nonce=5, SrcChain=777, DstChain=888, PayloadLen=16
    payload = b"SecureAAVData123"
    header = struct.pack(">QIII", 5, 777, 888, len(payload))
    full_packet = header + payload
    
    # 2. Split the payload into intentional tiny 4-byte fragments
    chunks = [full_packet[i:i+4] for i in range(0, len(full_packet), 4)]
    print(f"[*] Payload fragmented into {len(chunks)} blocks for evasion testing.")
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', 8082))
        
        # 3. Stream fragments with a micro-delay to test loop-reassembly
        for chunk in chunks:
            s.sendall(chunk)
            time.sleep(0.05) # 50ms propagation delay simulating network jitter
            
        print("[+] All fragmented frames dispatched down active socket wire.")
        s.close()
    except Exception as e:
        print(f"[-] Connection failed (Ensure your proxy service is running): {e}")

if __name__ == "__main__":
    run_fragmentation_test()
