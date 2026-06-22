import sys
import os
import logging

# Adjust path to import from workspace
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automate_login import verify_documents

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

target_dir = r"c:\Users\admin\Desktop\robbinmahindra\documents\HARISH M B"
customer_name = "HARISH M B"

# Mock claim_details and old_vehicle_details based on actual values from HARISH M B's case
claim_details = {
    "New vehicle Model Group": "THAR ROXX",
    "Chassis No": "T2E37675",
    "Approved Total Amount": "20000"
}
old_vehicle_details = {
    "Chassis No": "COD2026046DL13CQ0333",
    "Reg. No": "DL13CQ0333",
    "Customer Name": "HARISH M B"
}

print("Running pipeline verification...")
issues = verify_documents(
    target_dir=target_dir,
    customer_name=customer_name,
    claim_details=claim_details,
    old_vehicle_details=old_vehicle_details,
    claim_choice=1
)

print("\n--- Validation Issues Reported ---")
if issues:
    for idx, iss in enumerate(issues):
        print(f"{idx+1}. {iss}")
else:
    print("SUCCESS: No issues reported!")
