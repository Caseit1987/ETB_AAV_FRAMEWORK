#!/bin/bash
echo "=================================================================="
echo "          ETB AAV LAYERZERO - AUTOMATED TEST ENGINE               "
echo "=================================================================="

echo -e "\n[*] 1. Running Low-Level Parsing Tests..."
python protocol_parser.py
if [ $? -eq 0 ]; then echo "[PASS] Protocol parser is structurally sound."; else echo "[FAIL] Protocol parser broken."; exit 1; fi

echo -e "\n[*] 2. Executing Macro Invariant Test Vectors..."
python demo_etb.py
if [ $? -eq 0 ]; then echo "[PASS] All structural invariants held safely."; else echo "[FAIL] Invariant block triggered error."; exit 1; fi

echo -e "\n[*] 3. Running Nanosecond Side-Channel Timing Audit..."
python timing_attack.py
if [ $? -eq 0 ]; then echo "[PASS] Cryptographic comparisons are safely constant-time."; else echo "[FAIL] Timing leak detected."; exit 1; fi

echo -e "\n=================================================================="
echo "      SUCCESS: BUILD v1.0.0 ACCREDITED FOR PRODUCTION RELEASE     "
echo "=================================================================="
