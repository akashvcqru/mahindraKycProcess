import sys
import os
from rapidfuzz import fuzz

sys.path.append(os.path.abspath("."))
from automate_login import find_chassis_in_text, compare_values_robust

# Mock data
claim_details = {"Chassis No": "MA3T6D15293"}
old_vehicle_details = {"Chassis No": "HR08K1032CHAS123"}

def test_cod_validation(cert_no, text, expected_new_chassis, expected_old_chassis):
    issues = []
    
    # 1. Certificate of Deposit number must match old vehicle Chassis No
    if cert_no and expected_old_chassis:
        status_cert, score_cert = compare_values_robust(cert_no, expected_old_chassis)
        if status_cert.startswith("MATCH"):
            print(f"  - Certificate No Validation: PASS (Certificate '{cert_no}' matches old chassis '{expected_old_chassis}')")
        else:
            print(f"  - Certificate No Validation: FAIL")
            issues.append("Certificate No Mismatch")
            
    # 2. Chassis Number in the document (new vehicle chassis) last 8 characters must match dashboard claim details
    if expected_new_chassis:
        matched_new = find_chassis_in_text(text, expected_new_chassis, match_last_8=True)
        if matched_new:
            print(f"  - Document Chassis Validation: PASS (Found chassis matching last 8 of new vehicle: '{matched_new}')")
        else:
            print(f"  - Document Chassis Validation: FAIL")
            issues.append("New Chassis Mismatch")
            
    return issues

# Test Case 1: Both match perfectly
print("--- Test Case 1: Perfect Match ---")
text_1 = "Certificate of Deposit. New chassis is MA3T6D15293."
cert_no_1 = "HR08K1032CHAS123"
res_1 = test_cod_validation(cert_no_1, text_1, claim_details["Chassis No"], old_vehicle_details["Chassis No"])
print(f"Result (should be empty): {res_1}\n")

# Test Case 2: New chassis matches by last 8 characters only (e.g. text only contains last 8)
print("--- Test Case 2: New chassis last 8 match only ---")
text_2 = "Certificate of Deposit. New chassis: T6D15293."
cert_no_2 = "HR08K1032CHAS123"
res_2 = test_cod_validation(cert_no_2, text_2, claim_details["Chassis No"], old_vehicle_details["Chassis No"])
print(f"Result (should be empty): {res_2}\n")

# Test Case 3: New chassis mismatch (different last 8 characters)
print("--- Test Case 3: New chassis mismatch ---")
text_3 = "Certificate of Deposit. New chassis: T6D99999."
cert_no_3 = "HR08K1032CHAS123"
res_3 = test_cod_validation(cert_no_3, text_3, claim_details["Chassis No"], old_vehicle_details["Chassis No"])
print(f"Result (should have New Chassis Mismatch): {res_3}\n")

# Test Case 4: Certificate No mismatch
print("--- Test Case 4: Certificate No mismatch ---")
text_4 = "Certificate of Deposit. New chassis: MA3T6D15293."
cert_no_4 = "HR99K9999CHAS999"
res_4 = test_cod_validation(cert_no_4, text_4, claim_details["Chassis No"], old_vehicle_details["Chassis No"])
print(f"Result (should have Certificate No Mismatch): {res_4}\n")

# Test Case 5: Certificate OCR confusion match (e.g. 0 replaced by O)
print("--- Test Case 5: Certificate OCR confusion match ---")
text_5 = "Certificate of Deposit. New chassis: T6D15293."
cert_no_5 = "HRO8K1032CHAS123"  # O instead of 0
res_5 = test_cod_validation(cert_no_5, text_5, claim_details["Chassis No"], old_vehicle_details["Chassis No"])
print(f"Result (should be empty): {res_5}\n")
