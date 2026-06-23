import os
import sys
import logging

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Import the verify_documents function from automate_login.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from automate_login import verify_documents

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

target_dir = r"c:\Users\admin\Desktop\robbinmahindra\documents\Vijesh N Saigal"
customer_name = "Vijesh N Saigal"

# Mock values derived from logs and standard scheme mappings
# Mock values derived from logs and standard scheme mappings
claim_details = {
    "New vehicle Model Group": "THAR ROXX",
    "Invoice No": "INV27C000137",
    "Chassis No": "T2D21220"
}

old_vehicle_details = {
    "Relationship": "Self",
    "Customer Name": "Vijesh N Saigal",
    "Registration No": "DL1CU3705",
    "Vehicle Make": "Hyundai",
    "Vehicle Model": "Santro",
    "Chassis No": "COD202605590D1LCU3705"
}

# Set globals matching expected execution
globals()["CURRENT_ZONE"] = "SOUTH"
globals()["CURRENT_CITY"] = "BANGALORE"

print("Running verify_documents for Vijesh N Saigal...")
issues = verify_documents(
    target_dir=target_dir,
    customer_name=customer_name,
    claim_details=claim_details,
    old_vehicle_details=old_vehicle_details,
    claim_choice="scrappage",
    dashboard_dealer_name="SUTARIA AUTO CENTER",
    dashboard_scheme_type="scrappage"
)

print("\n==================================================")
print("VERDICT / ENCOUNTERED ISSUES:")
print("==================================================")
if issues:
    for issue in issues:
        print(f" - {issue}")
else:
    print(" APPROVED (No issues)")
print("==================================================")
