import sys
import os
import logging

workspace_dir = r"C:\Users\admin\Desktop\robbinmahindra"
sys.path.append(workspace_dir)

import automate_login

logging.basicConfig(level=logging.INFO)

target_dir = os.path.join(workspace_dir, "documents", "NAVEENA R")
customer_name = "NAVEENA R"
claim_choice = "1" # Loyalty
dashboard_dealer_name = "AUTOMOTIVE MANUFACTURES PVT. LTD"
dashboard_scheme_type = "welcome"

claim_details = {
    "New Vehicle Model": "VEERO",
    "New vehicle Model Group": "VEERO",
    "Invoice No": "INV27K000034",
    "Invoice Number": "INV27K000034",
    "Total Amount": "15000"
}

old_vehicle_details = {
    "Customer Name": "NAVEENA R",
    "Relationship": "Self"
}

issues = automate_login.verify_documents(
    target_dir=target_dir,
    customer_name=customer_name,
    claim_details=claim_details,
    old_vehicle_details=old_vehicle_details,
    claim_choice=claim_choice,
    dashboard_dealer_name=dashboard_dealer_name,
    dashboard_scheme_type=dashboard_scheme_type
)

print("\nValidation Complete. Issues reported:")
for issue in issues:
    print(f" - {issue}")
