import sys
import os
import logging

workspace_dir = r"C:\Users\admin\Desktop\robbinmahindra"
sys.path.append(workspace_dir)

import automate_login

logging.basicConfig(level=logging.INFO)

target_dir = os.path.join(workspace_dir, "documents", "Bhuvana M")
customer_name = "Bhuvana M"
claim_choice = "2"  # Exchange/Scrappage
dashboard_dealer_name = "ANANTCARS AUTO PVT. LTD."
dashboard_scheme_type = "scrappage"

claim_details = {
    "New Vehicle Model": "XUV3XO",
    "New vehicle Model Group": "XUV3XO",
    "Invoice No": "INV27E000363",
    "Invoice Number": "INV27E000363",
    "Total Amount": "30000",
    "Approved Total Amount": "30000"
}

old_vehicle_details = {
    "Customer Name": "Bhuvana M",
    "Relationship": "Self",
    "Registration No": "DL6CD7265",
    "Vehicle Make": "Maruti",
    "Vehicle Model": "Omni"
}

# Override globals to mock South Zone
automate_login.CURRENT_ZONE = "SOUTH"
automate_login.CURRENT_CITY = "BANGALORE"

issues = automate_login.verify_documents(
    target_dir=target_dir,
    customer_name=customer_name,
    claim_details=claim_details,
    old_vehicle_details=old_vehicle_details,
    claim_choice=claim_choice,
    dashboard_dealer_name=dashboard_dealer_name,
    dashboard_scheme_type=dashboard_scheme_type
)

print("\n=========================================")
print("Validation Complete. Issues reported:")
print("=========================================")
if issues:
    for issue in issues:
        print(f" - {issue}")
else:
    print("SUCCESS: No issues found! Status is APPROVED.")
print("=========================================")
