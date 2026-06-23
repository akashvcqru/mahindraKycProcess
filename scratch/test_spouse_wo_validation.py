"""
Quick offline test for Spouse W/O name validation.
Run: python scratch/test_spouse_wo_validation.py
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import automate_login
from unittest.mock import patch

automate_login.CURRENT_ZONE = "SOUTH"
automate_login.CURRENT_CITY = "CHENNAI"

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

def run(label, customer_name, old_vehicle_details, mock_files, mock_text_fn, expect_wo_issue=False):
    with patch("automate_login.extract_text_hybrid", side_effect=mock_text_fn), \
         patch("glob.glob", return_value=mock_files), \
         patch("os.path.exists", return_value=True):
        issues = automate_login.verify_documents(
            target_dir="/mock/dir",
            customer_name=customer_name,
            claim_details={"New vehicle Model Group": "BOLERO", "Relationship": "Spouse"},
            old_vehicle_details=old_vehicle_details,
            claim_choice=1
        )
    wo_issues = [i for i in issues if "Spouse Validation" in i or "W/O" in i]
    ok = (len(wo_issues) > 0) == expect_wo_issue
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"       issues={issues}")

print("\n=== Spouse W/O Validation Tests ===\n")

# 1. Aadhaar has W/O matching claimant → PASS
def adhar_wo_match(path):
    if "ADHAR" in path.upper():
        return "GOVERNMENT OF INDIA Aadhaar Priya Sharma W/O Rahul Sharma", True
    return "Ledger Priya Sharma Welcome Bonus 15000", True

run("Aadhaar W/O matches claimant → no issue",
    customer_name="Rahul Sharma",
    old_vehicle_details={"Relationship": "Spouse", "Customer Name": "Priya Sharma"},
    mock_files=["/mock/dir/ADHAR.pdf", "/mock/dir/LEDGER.pdf"],
    mock_text_fn=adhar_wo_match,
    expect_wo_issue=False)

# 2. Aadhaar has W/O NOT matching claimant → HOLD
def adhar_wo_mismatch(path):
    if "ADHAR" in path.upper():
        return "GOVERNMENT OF INDIA Aadhaar Priya Sharma W/O Suresh Kumar", True
    return "Ledger Priya Sharma Welcome Bonus 15000", True

run("Aadhaar W/O mismatches claimant → HOLD",
    customer_name="Rahul Sharma",
    old_vehicle_details={"Relationship": "Spouse", "Customer Name": "Priya Sharma"},
    mock_files=["/mock/dir/ADHAR.pdf", "/mock/dir/LEDGER.pdf"],
    mock_text_fn=adhar_wo_mismatch,
    expect_wo_issue=True)

# 3. No W/O field in document → warning only, no hold
def adhar_no_wo(path):
    if "ADHAR" in path.upper():
        return "GOVERNMENT OF INDIA Aadhaar Priya Sharma", True
    return "Ledger Priya Sharma Welcome Bonus 15000", True

run("No W/O field in Aadhaar → warning, no hold",
    customer_name="Rahul Sharma",
    old_vehicle_details={"Relationship": "Spouse", "Customer Name": "Priya Sharma"},
    mock_files=["/mock/dir/ADHAR.pdf", "/mock/dir/LEDGER.pdf"],
    mock_text_fn=adhar_no_wo,
    expect_wo_issue=False)

# 4. Non-Spouse relationship → W/O check does not fire
def adhar_wo_match_father(path):
    if "ADHAR" in path.upper():
        return "GOVERNMENT OF INDIA Aadhaar Raghul Senior W/O Rahul Sharma", True
    return "Ledger Lancy Babu Welcome Bonus 15000", True

run("Father relationship → W/O check does not fire",
    customer_name="Lancy Babu",
    old_vehicle_details={"Relationship": "Father", "Customer Name": "Raghul Senior"},
    mock_files=["/mock/dir/ADHAR.pdf", "/mock/dir/LEDGER.pdf"],
    mock_text_fn=adhar_wo_match_father,
    expect_wo_issue=False)

print()
