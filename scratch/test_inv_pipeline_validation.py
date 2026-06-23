import sys
import os
import logging

# Adjust path to import from workspace
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import automate_login
from automate_login import verify_documents

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

# Setup Globals
automate_login.CURRENT_ZONE = "SOUTH"
automate_login.CURRENT_CITY = "BANGALORE"

target_dir = r"c:\Users\admin\Desktop\robbinmahindra\documents\HARISH M B"
customer_name = "HARISH M B"

# Mock claim_details and old_vehicle_details based on actual values from HARISH M B's case
claim_details = {
    "New vehicle Model Group": "THAR ROXX",
    "Chassis No": "T2E37675",
    "Invoice No": "INV27Y000148",
    "Approved Total Amount": "20000",
    "Relationship": "Self"
}
old_vehicle_details = {
    "Chassis No": "COD2026046DL13CQ0333",
    "Reg. No": "DL13CQ0333",
    "Customer Name": "HARISH M B",
    "Relationship": "Self"
}

print("Running pipeline verification for Harish M B...")
issues = verify_documents(
    target_dir=target_dir,
    customer_name=customer_name,
    claim_details=claim_details,
    old_vehicle_details=old_vehicle_details,
    claim_choice=1 # 1 = Loyalty/Welcome
)

print("\n--- Validation Issues Reported ---")
if issues:
    for idx, iss in enumerate(issues):
        print(f"{idx+1}. {iss}")
else:
    print("SUCCESS: No issues reported! The claim is APPROVED.")
