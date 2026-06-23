import sys
import os
import logging

# Set up paths
workspace_dir = r"C:\Users\admin\Desktop\robbinmahindra"
sys.path.append(workspace_dir)

import automate_login

# Setup logging
logging.basicConfig(level=logging.INFO)

# Test parameters based on CAMS SHADES row
target_dir = os.path.join(workspace_dir, "documents", "CAMS SHADES")
customer_name = "CAMS SHADES"
claim_choice = "1" # Loyalty
dashboard_dealer_name = "SIDDHANTH MOTORS"
dashboard_scheme_type = "welcome"

# Mock claim details matching dashboard values from logs
claim_details = {
    "New Vehicle Model": "VEERO 1.5XXL SD V6",
    "New vehicle Model Group": "VEERO",
    "Invoice No": "INV27I000021",
    "Invoice Number": "INV27I000021",
    "Total Amount": "15000"
}

old_vehicle_details = {
    "Customer Name": "CAMS SHADES",
    "Relationship": "Self"
}

# Run verify_documents
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
