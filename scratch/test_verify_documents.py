import os
import sys
import logging

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Import the verify_documents function from automate_login.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from automate_login import verify_documents

# Let's run it on PRAVIN
target_dir = r"c:\Users\admin\Desktop\robbinmahindra\documents\PRAVIN"
customer_name = "PRAVIN"
claim_details = {
    "New vehicle Model Group": "XUV3XO",
    "Chassis No": "T2E77399"
}
old_vehicle_details = {
    "Registration No": "UP80CF1558",
    "Vehicle Make": "Ford",
    "Vehicle Model": "Figo",
    "Scheme": "Scrappage Bonus"
}

print("Running verify_documents...")
verify_documents(
    target_dir=target_dir,
    customer_name=customer_name,
    claim_details=claim_details,
    old_vehicle_details=old_vehicle_details,
    claim_choice=2
)
