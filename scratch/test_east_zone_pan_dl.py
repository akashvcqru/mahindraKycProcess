"""
Quick offline test for East Zone Bhubaneswar / Raipur mandatory PAN / DL check.
Run from workspace root: python scratch/test_east_zone_pan_dl.py
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import automate_login
from unittest.mock import patch

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

# ── helpers ──────────────────────────────────────────────────────────────────

def run(label, customer_name, old_vehicle_details, mock_files, mock_text_fn,
        zone="EAST", city="BHUBANESWAR", expect_issue=True):
    automate_login.CURRENT_ZONE = zone
    automate_login.CURRENT_CITY = city

    with patch("automate_login.extract_text_hybrid", side_effect=mock_text_fn), \
         patch("glob.glob", return_value=mock_files), \
         patch("os.path.exists", return_value=True):

        issues = automate_login.verify_documents(
            target_dir="/mock/dir",
            customer_name=customer_name,
            claim_details={"New vehicle Model Group": "BOLERO", "Relationship": "Self"},
            old_vehicle_details=old_vehicle_details,
            claim_choice=1
        )

    east_issues = [i for i in issues if "Mandatory PAN" in i or "Driving Licence" in i]
    ok = (len(east_issues) > 0) == expect_issue
    status = PASS if ok else FAIL
    print(f"  [{status}] {label}")
    if not ok:
        print(f"         issues={issues}")

# ── tests ─────────────────────────────────────────────────────────────────────

print("\n=== East Zone PAN / DL mandatory check tests ===\n")

# 1. No PAN / DL uploaded → should FAIL (issue raised)
run(
    label="Bhubaneswar — no PAN or DL uploaded → HOLD",
    customer_name="Lancy Babu",
    old_vehicle_details={"Relationship": "Self", "Customer Name": "Lancy Babu"},
    mock_files=["/mock/dir/LEDGER.pdf"],
    mock_text_fn=lambda p: ("Ledger Statement Lancy Babu Welcome Bonus 15000", True),
    zone="EAST", city="BHUBANESWAR",
    expect_issue=True
)

# 2. PAN uploaded with matching name → should PASS (no issue)
def text_pan_match(path):
    if "PAN" in path.upper():
        return "INCOME TAX DEPARTMENT PERMANENT ACCOUNT NUMBER Lancy Babu", True
    return "Ledger Statement Lancy Babu Welcome Bonus 15000", True

run(
    label="Bhubaneswar — valid PAN uploaded → PASS",
    customer_name="Lancy Babu",
    old_vehicle_details={"Relationship": "Self", "Customer Name": "Lancy Babu"},
    mock_files=["/mock/dir/PAN.pdf", "/mock/dir/LEDGER.pdf"],
    mock_text_fn=text_pan_match,
    zone="EAST", city="BHUBANESWAR",
    expect_issue=False
)

# 3. DL uploaded with matching name → should PASS (no issue)
def text_dl_match(path):
    if "DL" in path.upper() or "DRIVING" in path.upper():
        return "DRIVING LICENCE TRANSPORT AUTHORITY Lancy Babu", True
    return "Ledger Statement Lancy Babu Welcome Bonus 15000", True

run(
    label="Raipur — valid DL uploaded → PASS",
    customer_name="Lancy Babu",
    old_vehicle_details={"Relationship": "Self", "Customer Name": "Lancy Babu"},
    mock_files=["/mock/dir/DL.pdf", "/mock/dir/LEDGER.pdf"],
    mock_text_fn=text_dl_match,
    zone="EAST", city="RAIPUR",
    expect_issue=False
)

# 4. Non-East zone (SOUTH) → check does NOT fire even without PAN/DL
run(
    label="South Zone — no PAN/DL → no East zone issue (PASS)",
    customer_name="Lancy Babu",
    old_vehicle_details={"Relationship": "Self", "Customer Name": "Lancy Babu"},
    mock_files=["/mock/dir/LEDGER.pdf"],
    mock_text_fn=lambda p: ("Ledger Statement Lancy Babu Welcome Bonus 15000", True),
    zone="SOUTH", city="CHENNAI",
    expect_issue=False
)

# 5. East zone but different city (PATNA) → check does NOT fire
run(
    label="East Zone Patna — no PAN/DL → no East zone issue (PASS)",
    customer_name="Lancy Babu",
    old_vehicle_details={"Relationship": "Self", "Customer Name": "Lancy Babu"},
    mock_files=["/mock/dir/LEDGER.pdf"],
    mock_text_fn=lambda p: ("Ledger Statement Lancy Babu Welcome Bonus 15000", True),
    zone="EAST", city="PATNA",
    expect_issue=False
)

print()
