import socket

def run_vulnerable_backend():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 8081))
    server.listen(5)
    print("📡 Vulnerable Application Logic running internally on port 8081...")
    
    while True:
        client, addr = server.accept()
        payload = client.recv(1024)
        
        # Flawed Application Logic: Blindly trusts input if it reaches this layer
        if b'\xff' in payload:
            print("🚨 [CRITICAL FLAWS TRIGGERED] Backend processed unauthorized transaction exploit payload!")
            client.send(b"EXPLOIT_SUCCESS")
        else:
            print("✅ Backend processed standard transaction.")
            client.send(b"TRANSACTION_COMPLETE")
        client.close()

if __name__ == "__main__":
    run_vulnerable_backend()
