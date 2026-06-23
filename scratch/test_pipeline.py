import os
import sys

# Add parent directory to sys.path to allow importing from automate_login
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from automate_login import verify_documents

# Mock website drawer details for LANCY BABU P
lancy_claim_details = {
    "New vehicle Model Group": "VEERO",
    "Chassis No": "MAIUVZCUXTGEA6867",
    "Invoice No": "INV27A000T26"
}

lancy_old_vehicle_details = {
    "Registration No": "DQZPP2239C",
    "Vehicle Make": "Others",
    "Vehicle Model": "Others"
}

# Mock website drawer details for SRaghul Selvam
raghul_claim_details = {
    "New vehicle Model Group": "THAR Roxx STAR EDN p AT RWD EWT/BR",
    "Chassis No": "T2E33121",
    "Invoice No": "INV27P000199"
}

raghul_old_vehicle_details = {
    "Registration No": "UK0416469",
    "Vehicle Make": "Maruti",
    "Vehicle Model": "Omni"
}

# Mock website drawer details for G NIVETHA
nivetha_claim_details = {
    "New vehicle Model Group": "THAR ROXX MX3 DMT RWD STL BLK/BR",
    "Chassis No": "T2E27718",
    "Invoice No": "INV27Y000103"
}

nivetha_old_vehicle_details = {
    "Registration No": "HR08K1032",
    "Vehicle Make": "Maruti",
    "Vehicle Model": "Alto"
}

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    documents_dir = os.path.abspath(os.path.join(script_dir, "..", "documents"))
    
    # 1. Run pipeline for LANCY BABU P (Loyalty / Welcome Claim Choice = "1")
    lancy_dir = os.path.join(documents_dir, "LANCY BABU P")
    print(f"\n==================================================")
    print(f"RUNNING PIPELINE FOR CUSTOMER: LANCY BABU P")
    print(f"==================================================")
    verify_documents(lancy_dir, "LANCY BABU P", lancy_claim_details, lancy_old_vehicle_details, claim_choice="1")
    
    # 2. Run pipeline for SRaghul Selvam (Loyalty Claim Choice = "1")
    raghul_dir = os.path.join(documents_dir, "SRaghul Selvam")
    print(f"\n==================================================")
    print(f"RUNNING PIPELINE FOR CUSTOMER: SRaghul Selvam")
    print(f"==================================================")
    verify_documents(raghul_dir, "SRaghul Selvam", raghul_claim_details, raghul_old_vehicle_details, claim_choice="1")
    
    # 3. Run pipeline for G NIVETHA (Loyalty Claim Choice = "1")
    nivetha_dir = os.path.join(documents_dir, "G NIVETHA")
    print(f"\n==================================================")
    print(f"RUNNING PIPELINE FOR CUSTOMER: G NIVETHA")
    print(f"==================================================")
    verify_documents(nivetha_dir, "G NIVETHA", nivetha_claim_details, nivetha_old_vehicle_details, claim_choice="1")

if __name__ == "__main__":
    main()
