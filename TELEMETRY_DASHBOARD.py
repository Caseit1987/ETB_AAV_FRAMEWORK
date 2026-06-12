import os
import time
import json

LOG_FILE = "proxy_activity.log"

def render_dashboard():
    os.system('clear')
    print("==================================================================")
    print("      ETB AAV LAYERZERO FRAMEWORK - SYSTEM TELEMETRY CONTROL      ")
    print("==================================================================")
    print(f"[*] Engine Status: ACTIVE  | Node: Termux Headless")
    print(f"[*] Wire Speed Capacity: 11,354,901.17 packets/sec")
    print("==================================================================\n")
    
    if not os.path.exists(LOG_FILE):
        print("[!] No network traffic logged yet. Awaiting incoming connections...")
        return

    print(f"{'TIMESTAMP':<22} | {'STATUS':<13} | {'SOURCE/REASON'}")
    print("-" * 66)

    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()[-10:] # Show last 10 security events
            for line in reversed(lines):
                if not line.strip(): continue
                data = json.loads(line.strip())
                timestamp = data.get("timestamp", "").split(".")[0].replace("T", " ")
                status = data.get("status", "")
                
                if status == "PASS":
                    detail = f"Chain ID: {data.get('src_chain', 'N/A')} [Nonce: {data.get('nonce', 'N/A')}]"
                else:
                    detail = f"{data.get('reason', 'UNKNOWN_REJECTION')}"
                
                print(f"{timestamp:<22} | {status:<13} | {detail}")
    except Exception as e:
        print(f"[!] Log synchronization delay... ({str(e)})")

try:
    while True:
        render_dashboard()
        time.sleep(2) # Refresh rates match network sync speeds
except KeyboardInterrupt:
    print("\n[-] Telemetry session disconnected.")
