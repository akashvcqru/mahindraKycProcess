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

target_dir = r"c:\Users\admin\Desktop\robbinmahindra\documents\ABILASHGOWDA A"
customer_name = "ABILASHGOWDA A"
claim_details = {
    "New vehicle Model Group": "VEERO",
    "Chassis No": "T6C17618",
    "Invoice No": "INV27Y00008"
}
old_vehicle_details = {
    "Registration No": "575127613148",
    "Vehicle Make": "Others",
    "Vehicle Model": "Others"
}

print("Running verify_documents for ABILASHGOWDA A...")
verify_documents(
    target_dir=target_dir,
    customer_name=customer_name,
    claim_details=claim_details,
    old_vehicle_details=old_vehicle_details,
    claim_choice=1
)
