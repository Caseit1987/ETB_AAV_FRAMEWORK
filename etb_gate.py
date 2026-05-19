import socket, json, os, threading, hashlib
from datetime import datetime
from protocol_parser import parse_layerzero_packet
from state_engine import TrustBoundaryState
from crypto_verify import verify_payload_authenticity

BIND_IP = "127.0.0.1"
BIND_PORT = 8082
BACKEND_PORT = 8081
MAX_CONCURRENT_CONNECTIONS = 50
CLIENT_TIMEOUT = 5.0
MAX_PAYLOAD_SIZE = 4096
BLACKLIST_FILE = "blacklist.txt"

connection_semaphore = threading.Semaphore(MAX_CONCURRENT_CONNECTIONS)
state_manager = TrustBoundaryState()

def get_blacklisted_ips():
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r") as f:
            return [line.strip() for line in f if line.strip()]
    return []

def recv_all(sock, max_size):
    data = b""
    sock.settimeout(CLIENT_TIMEOUT)
    try:
        while len(data) < max_size:
            chunk = sock.recv(max_size - len(data))
            if not chunk:
                break
            data += chunk
    except socket.timeout:
        pass
    return data

def handle_client(client, addr):
    with connection_semaphore:
        client_ip = addr if isinstance(addr, tuple) else str(addr)
        http_ok = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n"
        
        if client_ip in get_blacklisted_ips():
            try: client.sendall(http_ok + b'{"status":"BLOCKED"}')
            except: pass
            client.close()
            return
            
        raw_stream = recv_all(client, MAX_PAYLOAD_SIZE)
        if not raw_stream:
            client.close()
            return
            
        parsed = parse_layerzero_packet(raw_stream)
        if not parsed["valid"]:
            log_entry = {"timestamp": datetime.utcnow().isoformat(), "status": "FAIL_REJECTED", "reason": parsed["reason"]}
            with open("proxy_activity.log", "a") as log: log.write(json.dumps(log_entry) + "\n")
            rejection = f'{{"status":"REJECTED","reason":"{parsed["reason"]}"}}'.encode()
            try: client.sendall(http_ok + rejection)
            except: pass
            client.close()
            return
            
        nonce_ok, nonce_msg = state_manager.validate_and_update_nonce(parsed["src_chain"], parsed["nonce"])
        if not nonce_ok:
            log_entry = {"timestamp": datetime.utcnow().isoformat(), "status": "FAIL_REJECTED", "reason": nonce_msg}
            with open("proxy_activity.log", "a") as log: log.write(json.dumps(log_entry) + "\n")
            rejection = f'{{"status":"REJECTED","reason":"{nonce_msg}"}}'.encode()
            try: client.sendall(http_ok + rejection)
            except: pass
            client.close()
            return
            
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "PASS",
            "nonce": parsed["nonce"],
            "src_chain": parsed["src_chain"],
            "payload_hash": hashlib.sha256(parsed["payload"]).hexdigest()[:16]
        }
        with open("proxy_activity.log", "a") as log:
            log.write(json.dumps(log_entry) + "\n")
            
        try:
            backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backend.settimeout(CLIENT_TIMEOUT)
            backend.connect(("127.0.0.1", BACKEND_PORT))
            backend.sendall(parsed["payload"])
            response = recv_all(backend, MAX_PAYLOAD_SIZE)
            client.sendall(http_ok + response)
            backend.close()
        except:
            pass
        finally:
            client.close()

def run_etb_gate():
    gateway = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    gateway.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    gateway.bind((BIND_IP, BIND_PORT))
    gateway.listen(128)
    print(f"[+] Stateful Proxy listening on port {BIND_PORT}...")
    while True:
        try:
            client, addr = gateway.accept()
            t = threading.Thread(target=handle_client, args=(client, addr))
            t.daemon = True
            t.start()
        except KeyboardInterrupt:
            break
        except:
            pass

if __name__ == "__main__":
    run_etb_gate()
