import socket

def run_etb_gate():
    gateway = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    gateway.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Changed binding port from 8080 to 8082
    gateway.bind(('127.0.0.1', 8082))
    gateway.listen(5)
    print("🛡️ ETB AAV Validation Gate active and protecting perimeter on port 8082...")
    
    while True:
        client, addr = gateway.accept()
        payload = client.recv(1024)
        
        # VALIDATE: Structural Anomaly Detection Engine
        if b'\xff' in payload and not payload.startswith(b'\x53\x43\x41\x41\x56_TRUSTED'):
            print("🛑 [ETB INTERCEPTION] Anomaly detected! Aborting transaction at perimeter.")
            with open("/data/data/com.termux/files/home/SCDU_PERMANENT_LOG.txt", "a") as log:
                log.write("Timestamp: 2026-05-18, Status: Blocked, Layer: ETB_AAV_GATE\n")
            client.close()
        else:
            try:
                backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                backend.connect(('127.0.0.1', 8081))
                backend.send(payload)
                response = backend.recv(1024)
                client.send(response)
                backend.close()
            except ConnectionRefusedError:
                client.send(b"BACKEND_OFFLINE")
            client.close()

if __name__ == "__main__":
    run_etb_gate()
