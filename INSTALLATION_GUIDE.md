# ETB AAV LayerZero™ Hardware & Sidecar Installation Reference

This document provides system integration specifications for deploying the ETB AAV LayerZero Verification Core on embedded infrastructure platforms, bare-metal hardware interfaces, and micro-kernel network pipelines.

## 1. Hardware Interface Constraints & Memory Alignment
The `native_verifier` binary utilizes low-level register abstractions to read frames at line speed. The physical interface configuration must enforce the following boundaries:
* **Word Alignment**: Incoming frames must match standard 32-bit (4-byte) boundary alignment to completely avoid CPU memory allocation faults.
* **Ingress Mapping**: Interfacing hardware network cards (NICs) must pass packet memory arrays directly to the validation engine via pointer registers, avoiding any internal `memcpy` operations.

## 2. Headless Network Sidecar Deployment (Linux/Embedded Systems)
To run the proxy gate as a secure system daemon that screens traffic before it interacts with your central enterprise applications or liquidity modules, configure a standard system lifecycle control unit:

Create a service file at `/etc/systemd/system/etb-gate.service`:
```ini
[Unit]
Description=ETB LayerZero Network Ingress Proxy Gate
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/etb_framework
ExecStart=/usr/bin/python3 etb_gate.py
Restart=always
RestartSec=1
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

To initialize and monitor the background ingress firewall engine:
```bash
systemctl daemon-reload
systemctl enable etb-gate.service
systemctl start etb-gate.service
journalctl -u etb-gate.service -f
```

## 3. Production Verification Protocol
Following integration, run the system's automated internal diagnostic validation suite to test all boundaries:
`./run_production_tests.sh`
