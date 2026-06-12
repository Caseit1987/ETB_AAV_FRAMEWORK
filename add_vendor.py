import csv

new_targets = [
    ["Critical Telecom Corp", "sec.ops@telecom-example.com", "2026-06-11", "Pending", "N/A", "High-capacity network hardware provider."],
    ["Global ATM Solutions", "risk.mitigation@atm-example.com", "2026-06-11", "Pending", "N/A", "Targeting CDU firmware integration."]
]

pipeline_path = "legal_templates/vendor_pipeline.csv"

with open(pipeline_path, mode='a', newline='') as f:
    writer = csv.writer(f)
    for target in new_targets:
        writer.writerow(target)

print(f"[+] Successfully appended {len(new_targets)} high-value targets to {pipeline_path}")
