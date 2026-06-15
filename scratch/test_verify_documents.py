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

# Let's run it on LANCY BABU P
target_dir = r"c:\Users\admin\Desktop\robbinmahindra\documents\LANCY BABU P"
customer_name = "LANCY BABU P"
claim_details = {
    "New vehicle Model Group": "BOLERO NEO",
    "Chassis No": "MA1YV2RNYG2P266OO"
}
old_vehicle_details = {
    "Registration No": "KL-13-Q-1234",
    "Vehicle Make": "Mahindra",
    "Vehicle Model": "Bolero"
}

print("Running verify_documents...")
verify_documents(
    target_dir=target_dir,
    customer_name=customer_name,
    claim_details=claim_details,
    old_vehicle_details=old_vehicle_details,
    claim_choice=1
)
