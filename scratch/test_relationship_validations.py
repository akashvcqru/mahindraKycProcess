import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure we can import from automate_login
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import automate_login
from automate_login import classify_and_extract, verify_documents

class TestRelationshipValidations(unittest.TestCase):

    def test_classify_gst_document(self):
        # Test GST document classification and name matching
        text = "Form GST REG-06 Registration Certificate Goods and Services Tax Legal Name: Akash Mahindra"
        filename = "GST_Registration.pdf"
        
        res = classify_and_extract(
            file_path=filename,
            text=text,
            claim_customer_name="Akash Mahindra"
        )
        
        self.assertEqual(res["file_type"], "GST")
        self.assertEqual(res["validations"]["Name Match Status"], "MATCH")
        self.assertGreaterEqual(res["validations"]["Name Match Score"], 80)

    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_verify_documents_relationship_self(self, mock_exists, mock_glob, mock_extract):
        # Relationship "Self" -> no relationship document check required, should return no issues
        mock_exists.return_value = True
        mock_glob.return_value = ["/mock/dir/LEDGER.pdf"]
        
        # Mock extract_text_hybrid to return ledger content
        mock_extract.return_value = ("Ledger Statement for Lancy Babu, Welcome Bonus 15000", True)
        
        # Call verify_documents with relationship = "Self"
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="Lancy Babu",
            claim_details={"New vehicle Model Group": "BOLERO", "Relationship": "Self"},
            old_vehicle_details={"Relationship": "Self"},
            claim_choice=1
        )
        
        # Check that no relationship-specific errors were raised
        rel_issues = [iss for iss in issues if "Relationship" in iss or "GST" in iss or "Aadhaar" in iss]
        self.assertEqual(len(rel_issues), 0)

    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_verify_documents_relationship_self_name_mismatch_fails(self, mock_exists, mock_glob, mock_extract):
        # Relationship "Self" but name mismatches old owner name -> should trigger relative ID validation and fail because no Aadhaar/PAN is found
        mock_exists.return_value = True
        mock_glob.return_value = ["/mock/dir/LEDGER.pdf"]
        mock_extract.return_value = ("Ledger Statement for Lancy Babu, Welcome Bonus 15000", True)
        
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="Lancy Babu",
            claim_details={"New vehicle Model Group": "BOLERO", "Relationship": "Self"},
            old_vehicle_details={"Relationship": "Self", "Customer Name": "Raghul Senior"},
            claim_choice=1
        )
        
        # Should raise a relationship document check issue since names mismatch and no relative ID document was provided
        rel_issues = [iss for iss in issues if "Relationship document" in iss]
        self.assertEqual(len(rel_issues), 1)
        self.assertIn("No Aadhaar/PAN found for relative 'Raghul Senior'", rel_issues[0])

    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_verify_documents_relationship_self_name_mismatch_succeeds(self, mock_exists, mock_glob, mock_extract):
        # Relationship "Self" but name mismatches old owner name -> triggers relative ID validation, should succeed if relative ID is provided and matches old owner name
        mock_exists.return_value = True
        mock_glob.return_value = ["/mock/dir/ADHAR.pdf", "/mock/dir/LEDGER.pdf"]
        
        def mock_extract_text(pdf_path):
            if "ADHAR" in pdf_path:
                return "GOVERNMENT OF INDIA Aadhaar Raghul Senior", True
            return "Ledger Statement for Lancy Babu, Welcome Bonus 15000", True
        mock_extract.side_effect = mock_extract_text
        
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="Lancy Babu",
            claim_details={"New vehicle Model Group": "BOLERO", "Relationship": "Self"},
            old_vehicle_details={"Relationship": "Self", "Customer Name": "Raghul Senior"},
            claim_choice=1
        )
        
        # Should pass relationship checks because a valid Aadhaar matching the old owner's name was found
        rel_issues = [iss for iss in issues if "Relationship" in iss or "Aadhaar" in iss]
        self.assertEqual(len(rel_issues), 0)

    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_verify_documents_relationship_proprietor_success(self, mock_exists, mock_glob, mock_extract):
        # Relationship "Proprietor" -> needs matching GST document
        mock_exists.return_value = True
        mock_glob.return_value = ["/mock/dir/GST_doc.pdf"]
        
        mock_extract.return_value = ("Form GST REG-06 Registration Certificate Legal Name: Akash Mahindra", True)
        
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="Akash Mahindra",
            claim_details={"Relationship": "Proprietor"},
            old_vehicle_details={"Relationship": "Proprietor"},
            claim_choice=1
        )
        
        # Should be verified, so no relationship issue
        rel_issues = [iss for iss in issues if "Relationship" in iss or "GST" in iss]
        self.assertEqual(len(rel_issues), 0)

    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_verify_documents_relationship_proprietor_failure(self, mock_exists, mock_glob, mock_extract):
        # Relationship "Proprietor" -> missing GST document
        mock_exists.return_value = True
        mock_glob.return_value = ["/mock/dir/ADHAR.pdf"] # only aadhaar
        
        mock_extract.return_value = ("GOVERNMENT OF INDIA Aadhaar Akash Mahindra", True)
        
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="Akash Mahindra",
            claim_details={"Relationship": "Proprietor"},
            old_vehicle_details={"Relationship": "Proprietor"},
            claim_choice=1
        )
        
        # Should fail relationship checks with GST missing
        rel_issues = [iss for iss in issues if "Relationship document" in iss]
        self.assertEqual(len(rel_issues), 1)
        self.assertIn("No matching GST document found for Proprietor", rel_issues[0])

    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_verify_documents_relationship_relative_success(self, mock_exists, mock_glob, mock_extract):
        # Relationship "Father" -> checks relative ID Aadhaar or PAN
        mock_exists.return_value = True
        mock_glob.return_value = ["/mock/dir/ADHAR.pdf"]
        
        mock_extract.return_value = ("GOVERNMENT OF INDIA Aadhaar Raghul Senior", True)
        
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="Akash Mahindra",
            claim_details={"Relationship": "Father"},
            old_vehicle_details={"Relationship": "Father", "Customer Name": "Raghul Senior"},
            claim_choice=1
        )
        
        rel_issues = [iss for iss in issues if "Relationship" in iss or "Aadhaar" in iss]
        # Aadhaar name matches relative name "Raghul Senior" -> should succeed
        self.assertEqual(len(rel_issues), 0)

    def test_combined_ledger_conditions_south_missing(self):
        from automate_login import validate_ledger_conditions
        issues = []
        text = "Ledger account statement with completely other things"
        claim_details = {
            "Total Amount": "15000",
            "Claim Amount": "15000"
        }
        # South zone, Loyalty claim -> missing expected welcome bonus
        validate_ledger_conditions(text, "ledger.pdf", claim_details, "SOUTH", "BANGALORE", 1, issues)
        self.assertTrue(any("Expected entry containing" in iss for iss in issues))

    def test_combined_ledger_conditions_west_scheme_18(self):
        from automate_login import validate_ledger_conditions
        issues = []
        # Scheme 18% with correct amount
        text = "Scheme 18% 15000.0"
        claim_details = {
            "Total Amount": "15000",
            "Claim Amount": "15000"
        }
        # West zone, Exchange claim -> Scheme 18% matches and is cleaned
        validate_ledger_conditions(text, "ledger.pdf", claim_details, "WEST", "MUMBAI", 2, issues)
        self.assertEqual(len(issues), 0)

    def test_combined_ledger_conditions_north_mismatch(self):
        from automate_login import validate_ledger_conditions
        issues = []
        # Entry exists but amount mismatches
        text = "Green Bonus 10000.0"
        claim_details = {
            "Total Amount": "15000",
            "Claim Amount": "15000"
        }
        # North zone, Exchange claim -> Green Bonus mismatch
        validate_ledger_conditions(text, "ledger.pdf", claim_details, "NORTH", "DELHI", 2, issues)
        self.assertTrue(any("amount mismatch in ledger" in iss for iss in issues))

if __name__ == "__main__":
    unittest.main()
