import sys
import os
import logging

# Add parent directory to path so we can import automate_login
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import automate_login

logging.basicConfig(level=logging.INFO)

target_dir = r"C:\Users\admin\Desktop\robbinmahindra\documents\GOUTAM PAUL"
customer_name = "GOUTAM PAUL"

claim_details = {
    "dashboard_customer_names": [],
    "New vehicle Model Group": "VEERO"
}

old_vehicle_details = {
    "Relationship": "Self",
    "Customer Name": "GOUTAM PAUL"
}

# Run the common verification function on Goutam Paul's folder
issues = automate_login.common_verify_documents(
    target_dir,
    customer_name,
    claim_details=claim_details,
    old_vehicle_details=old_vehicle_details
)

print("\n--- RESULTS ---")
print(f"Issues found: {issues}")
print(f"Documents found and cached in CURRENT_ROW_DOCUMENTS: {len(automate_login.CURRENT_ROW_DOCUMENTS)}")
for doc in automate_login.CURRENT_ROW_DOCUMENTS:
    print(f"  Doc: {doc['file_name']}, Type: {doc['file_type']}, Validations: {doc['validations']}")
