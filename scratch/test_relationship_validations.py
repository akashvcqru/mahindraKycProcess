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

    @patch("automate_login.classify_and_extract")
    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_verify_documents_relationship_self_name_mismatch_succeeds(self, mock_exists, mock_glob, mock_extract, mock_classify):
        # Relationship "Self" but name mismatches old owner name -> triggers relative ID validation, should succeed if relative ID is provided and matches old owner name
        mock_exists.return_value = True
        mock_glob.return_value = ["/mock/dir/ADHAR.pdf", "/mock/dir/LEDGER.pdf"]
        
        mock_extract.side_effect = lambda path: (
            "GOVERNMENT OF INDIA Aadhaar Raghul Senior (relative of Lancy Babu)" if "ADHAR" in path else "Ledger Statement for Lancy Babu, Welcome Bonus 15000",
            True
        )
        
        def mock_classify_func(file_path, text, name, *args, **kwargs):
            if "ADHAR" in file_path:
                return {
                    "file_type": "ADHAR",
                    "extracted_data": {
                        "Aadhaar Number": "123456789012",
                        "Name": "Raghul Senior",
                        "is_relative_doc": True,
                        "relative_owner_name": "Raghul Senior"
                    },
                    "validations": {
                        "Name Match Score": 100.0,
                        "Name Match Status": "MATCH"
                    }
                }
            return {
                "file_type": "LEDGER",
                "extracted_data": {"Customer Name": "Lancy Babu"},
                "validations": {"Name Match Score": 100.0, "Name Match Status": "MATCH"}
            }
        mock_classify.side_effect = mock_classify_func
        
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="Lancy Babu",
            claim_details={"New vehicle Model Group": "BOLERO", "Relationship": "Self"},
            old_vehicle_details={"Relationship": "Self", "Customer Name": "Raghul Senior"},
            claim_choice=1
        )
        
        # Should pass relationship checks because a valid Aadhaar matching the old owner's name was found and mentions the claimant name
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

    @patch("automate_login.classify_and_extract")
    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_verify_documents_relationship_relative_success(self, mock_exists, mock_glob, mock_extract, mock_classify):
        # Relationship "Father" -> checks relative ID Aadhaar or PAN
        mock_exists.return_value = True
        mock_glob.return_value = ["/mock/dir/ADHAR.pdf"]
        
        mock_extract.return_value = ("GOVERNMENT OF INDIA Aadhaar Raghul Senior (father of Akash Mahindra)", True)
        
        mock_classify.return_value = {
            "file_type": "ADHAR",
            "extracted_data": {
                "Aadhaar Number": "123456789012",
                "Name": "Raghul Senior",
                "is_relative_doc": True,
                "relative_owner_name": "Raghul Senior"
            },
            "validations": {
                "Name Match Score": 100.0,
                "Name Match Status": "MATCH"
            }
        }
        
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="Akash Mahindra",
            claim_details={"Relationship": "Father"},
            old_vehicle_details={"Relationship": "Father", "Customer Name": "Raghul Senior"},
            claim_choice=1
        )
        
        rel_issues = [iss for iss in issues if "Relationship" in iss or "Aadhaar" in iss]
        # Aadhaar name matches relative name "Raghul Senior" and contains claimant name -> should succeed
        self.assertEqual(len(rel_issues), 0)

    def test_ledger_conditions_with_dashboard_total_amount(self):
        from automate_login import validate_ledger_conditions
        issues = []
        text = "Ledger Welcome Bonus payment 20000.0"
        claim_details = {
            "dashboard_total_amount": 20000.0
        }
        # East zone, Loyalty claim -> should match dashboard_total_amount
        validate_ledger_conditions(text, "ledger.pdf", claim_details, "EAST", "BHUBANESWAR", 1, issues)
        self.assertEqual(len(issues), 0)

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

    @patch("automate_login.verify_invoice_stamp_and_signatures")
    def test_validate_invoice_doc_amount_extraction(self, mock_sig):
        from automate_login import validate_invoice_doc
        mock_sig.return_value = (True, "GOOD", True, "GOOD")
        
        # Test case 1: Note : Scrappage Bonus Amount is Rs.20000.00/-.(inclusive of GST)
        text = "TAX INVOICE. Note : Scrappage Bonus Amount is Rs.20000.00/-.(inclusive of GST)"
        data = {
            "Vehicle Model": "XUV3XO",
            "Customer Name": "SAROJINEE",
            "Dealer Name": "ANANTCARS AUTO PVT. LTD.",
            "Invoice No": "INV123",
            "Invoice Date": "2026-06-23"
        }
        validations = {
            "Name Match Status": "MATCH",
            "Name Match Score": 100.0
        }
        issues = []
        # mock load_contribution_data to return a schema where XUV3XO has scrappage = 20000
        with patch("automate_login.load_contribution_data") as mock_load:
            mock_load.return_value = {
                "welcome": {},
                "scrappage": {"XUV3XO": 20000.0}
            }
            validate_invoice_doc(
                filename="invoice.pdf",
                pdf_path="/mock/dir/invoice.pdf",
                text=text,
                data=data,
                validations=validations,
                claim_details={"New vehicle Model Group": "XUV3XO", "Invoice No": "INV123"},
                company_name="ANANTCARS AUTO PVT. LTD.",
                customer_name="SAROJINEE",
                issues=issues,
                dashboard_scheme_type="scrappage"
            )
        # Should match and have 0 issues (since 20000.0 matches expected 20000.0)
        self.assertEqual(len(issues), 0)

    @patch("automate_login.verify_invoice_stamp_and_signatures")
    def test_validate_invoice_doc_amount_mismatch(self, mock_sig):
        from automate_login import validate_invoice_doc
        mock_sig.return_value = (True, "GOOD", True, "GOOD")
        
        # Test case 2: Note with incorrect amount, should report mismatch instead of failed to extract
        text = "TAX INVOICE. ote : Scrappage Bonus Amount is Rs.15000.00/-.(inclusive of GST)"
        data = {
            "Vehicle Model": "XUV3XO",
            "Customer Name": "SAROJINEE",
            "Dealer Name": "ANANTCARS AUTO PVT. LTD.",
            "Invoice No": "INV123",
            "Invoice Date": "2026-06-23"
        }
        validations = {
            "Name Match Status": "MATCH",
            "Name Match Score": 100.0
        }
        issues = []
        with patch("automate_login.load_contribution_data") as mock_load:
            mock_load.return_value = {
                "welcome": {},
                "scrappage": {"XUV3XO": 20000.0}
            }
            validate_invoice_doc(
                filename="invoice.pdf",
                pdf_path="/mock/dir/invoice.pdf",
                text=text,
                data=data,
                validations=validations,
                claim_details={"New vehicle Model Group": "XUV3XO", "Invoice No": "INV123"},
                company_name="ANANTCARS AUTO PVT. LTD.",
                customer_name="SAROJINEE",
                issues=issues,
                dashboard_scheme_type="scrappage"
            )
        # Should raise amount mismatch issue (and ignore signature check failure)
        mismatch_issues = [iss for iss in issues if "Amount mismatch" in iss]
        self.assertEqual(len(mismatch_issues), 1)
        self.assertIn("Extracted Bonus: 15000.0", mismatch_issues[0])

    def test_extract_total_amount_layout_a(self):
        from automate_login import extract_total_amount_from_row_7
        page = MagicMock()
        
        # Set up row_7 mocks
        row_7 = MagicMock()
        row_7.count.return_value = 1
        row_7.first = row_7
        row_7.is_visible.return_value = True
        
        tds_7 = MagicMock()
        tds_7.count.return_value = 0
        ths_7 = MagicMock()
        ths_7.count.return_value = 1
        
        def row_7_locator(sel):
            if "td" in sel:
                return tds_7
            elif "th" in sel:
                return ths_7
            return MagicMock()
        row_7.locator.side_effect = row_7_locator
        
        # Set up row_8 mocks
        row_8 = MagicMock()
        row_8.count.return_value = 1
        row_8.first = row_8
        row_8.is_visible.return_value = True
        
        tds_8 = MagicMock()
        tds_8.count.return_value = 1
        tds_8.first = tds_8
        tds_8.inner_text.return_value = "  Rs. 25,000.00/-  "
        row_8.locator.return_value = tds_8
        
        # Configure page locator behavior
        def page_locator_mock(sel):
            if "tr:nth-child(7)" in sel:
                return row_7
            elif "tr:nth-child(8)" in sel:
                return row_8
            return MagicMock()
            
        page.locator.side_effect = page_locator_mock
        
        val = extract_total_amount_from_row_7(page)
        self.assertEqual(val, 25000.0)

    def test_extract_total_amount_layout_b(self):
        from automate_login import extract_total_amount_from_row_7
        page = MagicMock()
        
        # Set up row_7 mocks
        row_7 = MagicMock()
        row_7.count.return_value = 1
        row_7.first = row_7
        row_7.is_visible.return_value = True
        
        # Layout B: td inside row_7
        tds = MagicMock()
        tds.count.return_value = 1
        tds.first = tds
        tds.inner_text.return_value = "  Rs. 30,000.00/-  "
        row_7.locator.side_effect = lambda sel: tds if "td" in sel else MagicMock()
        
        def page_locator_mock(sel):
            if "tr:nth-child(7)" in sel:
                return row_7
            return MagicMock()
        page.locator.side_effect = page_locator_mock
        
        val = extract_total_amount_from_row_7(page)
        self.assertEqual(val, 30000.0)

    def test_ledger_conditions_with_dashboard_total_amount_mismatch(self):
        from automate_login import validate_ledger_conditions
        issues = []
        text = "Ledger Welcome Bonus payment 15000.0"
        claim_details = {
            "dashboard_total_amount": 20000.0
        }
        # East zone, Loyalty claim -> mismatches dashboard_total_amount
        validate_ledger_conditions(text, "ledger.pdf", claim_details, "EAST", "BHUBANESWAR", 1, issues)
        self.assertTrue(any("Welcome Bonus amount mismatch" in iss for iss in issues))

    @patch("automate_login.classify_and_extract")
    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    @patch("automate_login.verify_ledger_stamp_and_signature")
    def test_verify_documents_ledger_with_dashboard_total_amount(self, mock_stamp, mock_exists, mock_glob, mock_extract, mock_classify):
        mock_exists.return_value = True
        mock_stamp.return_value = (True, "GOOD")
        
        # Mock classify_and_extract
        def mock_classify_func(file_path, text, claim_customer_name, claim_details=None, old_vehicle_details=None):
            if "ADHAR" in file_path:
                return {
                    "file_type": "ADHAR",
                    "extracted_data": {"Name": "Lancy Babu"},
                    "validations": {"Name Match Score": 100.0, "Name Match Status": "MATCH"}
                }
            return {
                "file_type": "LEDGER",
                "extracted_data": {"Customer Name": "Lancy Babu"},
                "validations": {"Name Match Score": 100.0, "Name Match Status": "MATCH"}
            }
        mock_classify.side_effect = mock_classify_func

        # Test 1: Amount matches dashboard_total_amount
        mock_glob.return_value = ["/mock/dir/LEDGER.pdf", "/mock/dir/ADHAR.pdf"]
        mock_extract.side_effect = lambda path: (
            "Ledger Welcome Bonus payment 20000.0" if "LEDGER" in path else "Aadhaar Lancy Babu Self",
            True
        )
        
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="Lancy Babu",
            claim_details={
                "Relationship": "Self",
                "Scheme": "Welcome Bonus",
                "dashboard_total_amount": 20000.0,
                "New vehicle Model Group": "BOLERO"
            },
            old_vehicle_details={},
            claim_choice=1
        )
        ledger_issues = [iss for iss in issues if "Ledger" in iss]
        self.assertEqual(len(ledger_issues), 0)

        # Test 2: Amount mismatches dashboard_total_amount
        mock_extract.side_effect = lambda path: (
            "Ledger Welcome Bonus payment 15000.0" if "LEDGER" in path else "Aadhaar Lancy Babu Self",
            True
        )
        issues_mismatch = verify_documents(
            target_dir="/mock/dir",
            customer_name="Lancy Babu",
            claim_details={
                "Relationship": "Self",
                "Scheme": "Welcome Bonus",
                "dashboard_total_amount": 20000.0,
                "New vehicle Model Group": "BOLERO"
            },
            old_vehicle_details={},
            claim_choice=1
        )
        ledger_mismatch_issues = [iss for iss in issues_mismatch if "Ledger" in iss and "Amount mismatch" in iss]
        self.assertEqual(len(ledger_mismatch_issues), 1)

    @patch("automate_login.verify_invoice_stamp_and_signatures")
    def test_validate_disclaimer_doc_success(self, mock_sig):
        from automate_login import validate_disclaimer_doc
        mock_sig.return_value = (True, "GOOD", True, "GOOD")

        # Disclaimer date is equal to invoice date (past) and matches
        text = "CUSTOMER DISCLAIMER CONFIRM WELCOME DEALER VEHICLE CHASSIS ENGINE INVOICE"
        data = {
            "Customer Name": "Lancy Babu",
            "Registration No": "DL9CJ2283",
            "Vehicle Make": "Mahindra",
            "Vehicle Model": "BOLERO",
            "New Vehicle Model": "BOLERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026",
            "Disclaimer Date": "19/05/2026",
            "Welcome Bonus Amount": "15000"
        }
        validations = {"Name Match Status": "MATCH", "Name Match Score": 100.0}
        claim_details = {
            "New vehicle Model Group": "BOLERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026"
        }
        old_vehicle_details = {
            "Registration No": "DL9CJ2283",
            "Vehicle Make": "Mahindra",
            "Vehicle Model": "BOLERO"
        }
        issues = []
        
        with patch("automate_login.load_contribution_data") as mock_load:
            mock_load.return_value = {
                "welcome": {"BOLERO": [{"city": "COMMON", "amount": 15000.0}]},
                "scrappage": {}
            }
            validate_disclaimer_doc(
                filename="disclaimer.pdf",
                pdf_path="/mock/dir/disclaimer.pdf",
                text=text,
                data=data,
                validations=validations,
                claim_details=claim_details,
                old_vehicle_details=old_vehicle_details,
                claim_choice=1,
                dashboard_scheme_type="welcome",
                company_name="Mahindra",
                customer_name="Lancy Babu",
                issues=issues
            )
        self.assertEqual(len(issues), 0)

    @patch("automate_login.verify_invoice_stamp_and_signatures")
    def test_validate_disclaimer_doc_date_before_invoice(self, mock_sig):
        from automate_login import validate_disclaimer_doc
        mock_sig.return_value = (True, "GOOD", True, "GOOD")

        # Disclaimer date is before invoice date
        text = "CUSTOMER DISCLAIMER CONFIRM WELCOME DEALER VEHICLE CHASSIS ENGINE INVOICE"
        data = {
            "Customer Name": "Lancy Babu",
            "Registration No": "DL9CJ2283",
            "Vehicle Make": "Mahindra",
            "Vehicle Model": "BOLERO",
            "New Vehicle Model": "BOLERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026",
            "Disclaimer Date": "18/05/2026",  # 1 day before
            "Welcome Bonus Amount": "15000"
        }
        validations = {"Name Match Status": "MATCH", "Name Match Score": 100.0}
        claim_details = {
            "New vehicle Model Group": "BOLERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026"
        }
        issues = []
        
        with patch("automate_login.load_contribution_data") as mock_load:
            mock_load.return_value = {
                "welcome": {"BOLERO": [{"city": "COMMON", "amount": 15000.0}]},
                "scrappage": {}
            }
            validate_disclaimer_doc(
                filename="disclaimer.pdf",
                pdf_path="/mock/dir/disclaimer.pdf",
                text=text,
                data=data,
                validations=validations,
                claim_details=claim_details,
                old_vehicle_details=None,
                claim_choice=1,
                dashboard_scheme_type="welcome",
                company_name="Mahindra",
                customer_name="Lancy Babu",
                issues=issues
            )
        self.assertTrue(any("before invoice date" in iss for iss in issues))

    @patch("automate_login.verify_invoice_stamp_and_signatures")
    def test_validate_disclaimer_doc_date_exceeds_one_month(self, mock_sig):
        from automate_login import validate_disclaimer_doc
        mock_sig.return_value = (True, "GOOD", True, "GOOD")

        # Disclaimer date is after claim date
        text = "CUSTOMER DISCLAIMER CONFIRM WELCOME DEALER VEHICLE CHASSIS ENGINE INVOICE"
        data = {
            "Customer Name": "Lancy Babu",
            "Registration No": "DL9CJ2283",
            "Vehicle Make": "Mahindra",
            "Vehicle Model": "BOLERO",
            "New Vehicle Model": "BOLERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026",
            "Disclaimer Date": "12/06/2026",
            "Welcome Bonus Amount": "15000"
        }
        validations = {"Name Match Status": "MATCH", "Name Match Score": 100.0}
        claim_details = {
            "New vehicle Model Group": "BOLERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026",
            "dashboard_claim_date": "10/06/2026"
        }
        issues = []
        
        with patch("automate_login.load_contribution_data") as mock_load:
            mock_load.return_value = {
                "welcome": {"BOLERO": [{"city": "COMMON", "amount": 15000.0}]},
                "scrappage": {}
            }
            validate_disclaimer_doc(
                filename="disclaimer.pdf",
                pdf_path="/mock/dir/disclaimer.pdf",
                text=text,
                data=data,
                validations=validations,
                claim_details=claim_details,
                old_vehicle_details=None,
                claim_choice=1,
                dashboard_scheme_type="welcome",
                company_name="Mahindra",
                customer_name="Lancy Babu",
                issues=issues
            )
        self.assertTrue(any("is after claim date" in iss for iss in issues))

    @patch("automate_login.verify_invoice_stamp_and_signatures")
    def test_validate_disclaimer_doc_date_before_invoice(self, mock_sig):
        from automate_login import validate_disclaimer_doc
        mock_sig.return_value = (True, "GOOD", True, "GOOD")

        # Disclaimer date is before invoice date
        text = "CUSTOMER DISCLAIMER CONFIRM WELCOME DEALER VEHICLE CHASSIS ENGINE INVOICE"
        data = {
            "Customer Name": "Lancy Babu",
            "Registration No": "DL9CJ2283",
            "Vehicle Make": "Mahindra",
            "Vehicle Model": "BOLERO",
            "New Vehicle Model": "BOLERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026",
            "Disclaimer Date": "18/05/2026",
            "Welcome Bonus Amount": "15000"
        }
        validations = {"Name Match Status": "MATCH", "Name Match Score": 100.0}
        claim_details = {
            "New vehicle Model Group": "BOLERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026",
            "dashboard_claim_date": "10/06/2026"
        }
        issues = []
        
        with patch("automate_login.load_contribution_data") as mock_load:
            mock_load.return_value = {
                "welcome": {"BOLERO": [{"city": "COMMON", "amount": 15000.0}]},
                "scrappage": {}
            }
            validate_disclaimer_doc(
                filename="disclaimer.pdf",
                pdf_path="/mock/dir/disclaimer.pdf",
                text=text,
                data=data,
                validations=validations,
                claim_details=claim_details,
                old_vehicle_details=None,
                claim_choice=1,
                dashboard_scheme_type="welcome",
                company_name="Mahindra",
                customer_name="Lancy Babu",
                issues=issues
            )
        self.assertTrue(any("is before invoice date" in iss for iss in issues))

    @patch("automate_login.verify_invoice_stamp_and_signatures")
    def test_validate_disclaimer_doc_invoice_mismatch(self, mock_sig):
        from automate_login import validate_disclaimer_doc
        mock_sig.return_value = (True, "GOOD", True, "GOOD")

        # Invoice number and invoice date mismatches
        text = "CUSTOMER DISCLAIMER CONFIRM WELCOME DEALER VEHICLE CHASSIS ENGINE INVOICE"
        data = {
            "Customer Name": "Lancy Babu",
            "Registration No": "DL9CJ2283",
            "Vehicle Make": "Mahindra",
            "Vehicle Model": "BOLERO",
            "New Vehicle Model": "BOLERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-999",  # mismatches
            "Invoice Date": "20/05/2026",  # mismatches
            "Disclaimer Date": "20/05/2026",
            "Welcome Bonus Amount": "15000"
        }
        validations = {"Name Match Status": "MATCH", "Name Match Score": 100.0}
        claim_details = {
            "New vehicle Model Group": "BOLERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026"
        }
        issues = []
        
        with patch("automate_login.load_contribution_data") as mock_load:
            mock_load.return_value = {
                "welcome": {"BOLERO": [{"city": "COMMON", "amount": 15000.0}]},
                "scrappage": {}
            }
            validate_disclaimer_doc(
                filename="disclaimer.pdf",
                pdf_path="/mock/dir/disclaimer.pdf",
                text=text,
                data=data,
                validations=validations,
                claim_details=claim_details,
                old_vehicle_details=None,
                claim_choice=1,
                dashboard_scheme_type="welcome",
                company_name="Mahindra",
                customer_name="Lancy Babu",
                issues=issues
            )
        self.assertTrue(any("Invoice No mismatch" in iss for iss in issues))
        self.assertTrue(any("Invoice Date mismatch" in iss for iss in issues))

    @patch("automate_login.classify_and_extract")
    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_verify_documents_vahan_screenshot_success(self, mock_exists, mock_glob, mock_extract, mock_classify):
        mock_exists.return_value = True
        mock_glob.return_value = ["/mock/dir/VAHANSCREENSHOT-123.pdf"]
        
        mock_extract.return_value = ("Chassis Number Engine Number Certificate Deposit MAINSZNP1T2D70903 NPTZD89987 COD20260550DL7CA0858", True)
        
        mock_classify.return_value = {
            "file_type": "COD",
            "extracted_data": {
                "Certificate No": "COD2O26",
                "Registration No": None,
                "User Name": None
            },
            "validations": {
                "Name Match Score": 0.0,
                "Name Match Status": "MISMATCH"
            }
        }
        
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="LALU PRASAD RANA",
            claim_details={
                "Relationship": "Self",
                "Chassis No": "T2D70903",
                "New vehicle Model Group": "XUV3XO"
            },
            old_vehicle_details={
                "Chassis No": "COD20260550DL7CA0858",
                "Reg. No": "DL7CA0858",
                "Customer Name": "LALU PRASAD RANA"
            },
            claim_choice=1
        )
        
        cod_issues = [iss for iss in issues if "COD" in iss or "Vahan" in iss]
        self.assertEqual(len(cod_issues), 0)

    @patch("automate_login.classify_and_extract")
    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_verify_documents_vahan_screenshot_mismatch(self, mock_exists, mock_glob, mock_extract, mock_classify):
        mock_exists.return_value = True
        mock_glob.return_value = ["/mock/dir/VAHANSCREENSHOT-123.pdf"]
        
        mock_extract.return_value = ("Chassis Number Engine Number Certificate Deposit MAINSZNP1T2D70000 NPTZD89987 COD20260550DL7CA0000", True)
        
        mock_classify.return_value = {
            "file_type": "COD",
            "extracted_data": {
                "Certificate No": "COD2O26",
                "Registration No": None,
                "User Name": None
            },
            "validations": {
                "Name Match Score": 0.0,
                "Name Match Status": "MISMATCH"
            }
        }
        
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="LALU PRASAD RANA",
            claim_details={
                "Relationship": "Self",
                "Chassis No": "T2D70903",
                "New vehicle Model Group": "XUV3XO"
            },
            old_vehicle_details={
                "Chassis No": "COD20260550DL7CA0858",
                "Reg. No": "DL7CA0858",
                "Customer Name": "LALU PRASAD RANA"
            },
            claim_choice=1
        )
        
        cod_issues = [iss for iss in issues if "COD" in iss]
        self.assertEqual(len(cod_issues), 2)
        self.assertTrue(any("Expected Certificate of Deposit 'COD20260550DL7CA0858' not found" in iss for iss in cod_issues))
        self.assertTrue(any("Expected New Vehicle Chassis 'T2D70903' not found" in iss for iss in cod_issues))

    @patch("requests.post")
    @patch("fitz.open")
    def test_validate_invoice_declaration_relationship_success(self, mock_fitz, mock_post):
        from automate_login import validate_invoice_declaration_relationship
        
        # Mock fitz document rendering first page to base64
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"fake_image_bytes"
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.load_page.return_value = mock_page
        mock_doc.__len__.return_value = 1
        mock_fitz.return_value = mock_doc
        
        # Mock requests.post response from OpenAI Vision API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"printed_name_invoice": "Lancy Babu", "printed_name_disclaimer": "Lancy Babu", "handwritten_name_invoice": "Lancy Babu", "handwritten_name_disclaimer": "Lancy Babu", "stamp_present_invoice": true, "stamp_present_disclaimer": true, "signature_present_invoice": true, "signature_present_disclaimer": true, "scheme_name": "Welcome Bonus", "scheme_amount": "15000", "image_quality": "GOOD", "confidence_score": 95, "remarks": []}'
                }
            }]
        }
        mock_post.return_value = mock_response
        
        res = validate_invoice_declaration_relationship("/mock/invoice.pdf", "/mock/declaration.pdf")
        
        self.assertEqual(res["status"], "APPROVE")
        self.assertEqual(res["printed_name_invoice"], "Lancy Babu")
        self.assertEqual(res["printed_name_disclaimer"], "Lancy Babu")
        self.assertEqual(res["printed_name_match_score"], 100)
        self.assertEqual(res["handwritten_name_match_score"], 100)
        self.assertEqual(res["printed_vs_handwritten_match_score"], 100)
        self.assertTrue(res["stamp_present"])
        self.assertTrue(res["signature_present"])
        self.assertEqual(res["scheme_name"], "Welcome Bonus")
        self.assertEqual(res["scheme_amount"], "15000")
        self.assertEqual(res["image_quality"], "GOOD")
        self.assertEqual(res["confidence_score"], 95)
        self.assertEqual(len(res["hold_reasons"]), 0)

    @patch("requests.post")
    @patch("fitz.open")
    def test_validate_invoice_declaration_relationship_mismatch(self, mock_fitz, mock_post):
        from automate_login import validate_invoice_declaration_relationship
        
        # Mock fitz
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"fake_image_bytes"
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.load_page.return_value = mock_page
        mock_doc.__len__.return_value = 1
        mock_fitz.return_value = mock_doc
        
        # Mock requests.post response from OpenAI Vision API with a printed name mismatch and missing signature on invoice
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"printed_name_invoice": "BALARAM JENA", "printed_name_disclaimer": "LALU PRASAD RANA", "handwritten_name_invoice": null, "handwritten_name_disclaimer": "Lalu prasad rana", "stamp_present_invoice": true, "stamp_present_disclaimer": true, "signature_present_invoice": false, "signature_present_disclaimer": true, "scheme_name": "Scrappage Bonus", "scheme_amount": "30000", "image_quality": "GOOD", "confidence_score": 90, "remarks": ["Printed name mismatch", "Invoice signature missing"]}'
                }
            }]
        }
        mock_post.return_value = mock_response
        
        res = validate_invoice_declaration_relationship("/mock/invoice.pdf", "/mock/declaration.pdf")
        
        self.assertEqual(res["status"], "HOLD")
        self.assertEqual(res["printed_name_invoice"], "BALARAM JENA")
        self.assertEqual(res["printed_name_disclaimer"], "LALU PRASAD RANA")
        self.assertLess(res["printed_name_match_score"], 80)
        self.assertFalse(res["signature_present"])
        self.assertIn("Printed name mismatch", res["hold_reasons"])
        self.assertIn("Signature missing", res["hold_reasons"])
        self.assertIn("Handwritten name mismatch", res["hold_reasons"])

    @patch("automate_login.validate_invoice_declaration_relationship")
    @patch("automate_login.classify_and_extract")
    @patch("automate_login.extract_text_hybrid")
    @patch("glob.glob")
    @patch("os.path.exists")
    def test_verify_documents_cross_validation_integration(self, mock_exists, mock_glob, mock_extract, mock_classify, mock_cross):
        mock_exists.return_value = True
        mock_glob.return_value = ["/mock/dir/INVOICE.pdf", "/mock/dir/DISCLAIMER.pdf"]
        
        mock_extract.return_value = ("some text", True)
        
        # Mock classification so one is INVOICE and one is DISCLAIMER
        def mock_classify_func(file_path, text, *args, **kwargs):
            if "INVOICE" in file_path:
                return {
                    "file_type": "INVOICE",
                    "extracted_data": {"Customer Name": "Lancy Babu"},
                    "validations": {"Name Match Status": "MATCH", "Name Match Score": 100.0}
                }
            else:
                return {
                    "file_type": "DISCLAIMER",
                    "extracted_data": {"Customer Name": "Lancy Babu"},
                    "validations": {"Name Match Status": "MATCH", "Name Match Score": 100.0}
                }
        mock_classify.side_effect = mock_classify_func
        
        # Mock cross-validation to return a HOLD status
        mock_cross.return_value = {
            "status": "HOLD",
            "hold_reasons": ["Signature missing", "Stamp missing"],
            "remarks": ["Signature mismatch on invoice", "Stamp missing on declaration"]
        }
        
        # Run verify_documents
        issues = verify_documents(
            target_dir="/mock/dir",
            customer_name="Lancy Babu",
            claim_details={"Relationship": "Self"},
            old_vehicle_details=None,
            claim_choice=1
        )
        
        # The issues list should contain the cross-validation mismatch reasons
        cross_issues = [iss for iss in issues if "Cross-Validation Mismatch" in iss]
        self.assertEqual(len(cross_issues), 2)
        self.assertTrue(any("Signature mismatch on invoice" in iss for iss in cross_issues))
        self.assertTrue(any("Stamp missing on declaration" in iss for iss in cross_issues))

    def test_parse_custom_rows(self):
        from automate_login import parse_custom_rows
        # Test basic comma separated
        self.assertEqual(parse_custom_rows("1,3,5", 5), [0, 2, 4])
        # Test ranges
        self.assertEqual(parse_custom_rows("2-4", 5), [1, 2, 3])
        # Test mixture
        self.assertEqual(parse_custom_rows("1-3,5", 5), [0, 1, 2, 4])
        # Test out of bounds (should ignore)
        self.assertEqual(parse_custom_rows("1,3,6", 5), [0, 2])
        # Test duplicates
        self.assertEqual(parse_custom_rows("1,1,2-3,2", 5), [0, 1, 2])
        # Test empty or invalid
        self.assertEqual(parse_custom_rows("", 5), [])
        self.assertEqual(parse_custom_rows("abc", 5), [])

    @patch("openpyxl.Workbook")
    def test_excel_records_generation(self, mock_workbook_class):
        from automate_login import create_excel_results
        mock_wb = MagicMock()
        mock_ws = MagicMock()
        mock_wb.active = mock_ws
        mock_workbook_class.return_value = mock_wb
        
        excel_records = [
            {
                "row_num": 1,
                "customer_name": "Lancy Babu",
                "status": "APPROVED",
                "hold_reasons": "",
                "date_processed": "2026-06-23 12:00:00"
            },
            {
                "row_num": 3,
                "customer_name": "Akash Mahindra",
                "status": "HOLD",
                "hold_reasons": "Stamp missing",
                "date_processed": "2026-06-23 12:05:00"
            }
        ]
        
        excel_path = "/mock/path/kyc_process_results.xlsx"
        success = create_excel_results(excel_records, excel_path)
        
        self.assertTrue(success)
        # Ensure workbook was saved to the correct path
        mock_wb.save.assert_called_once_with(excel_path)
        # Ensure correct headers were appended first
        mock_ws.append.assert_any_call(["Row Number", "Customer Name", "Status", "Hold Reasons / Remarks", "Processed Date"])
        # Ensure records were appended
        mock_ws.append.assert_any_call([1, "Lancy Babu", "APPROVED", "", "2026-06-23 12:00:00"])
        mock_ws.append.assert_any_call([3, "Akash Mahindra", "HOLD", "Stamp missing", "2026-06-23 12:05:00"])

    def test_validate_east_zone_old_vehicle(self):
        from automate_login import validate_east_zone_old_vehicle
        
        # Test Case 1: Both fields readable, no PAN/DL found -> FAIL
        res1 = validate_east_zone_old_vehicle("MA1UV2CVXT6E17381", "UP16AB1234")
        self.assertEqual(res1["east_zone_validation"], "FAIL")
        self.assertEqual(res1["detected_document_type"], "UNKNOWN")
        self.assertEqual(res1["detected_value"], "")
        self.assertIn("PAN or Driving Licence not found", res1["validation_reason"])
        
        # Test Case 2: Valid PAN in Chassis No -> PASS
        res2 = validate_east_zone_old_vehicle("ABCDE1234F", "UP16AB1234")
        self.assertEqual(res2["east_zone_validation"], "PASS")
        self.assertEqual(res2["detected_document_type"], "PAN")
        self.assertEqual(res2["detected_value"], "ABCDE1234F")
        self.assertIn("Valid PAN found in Chassis No", res2["validation_reason"])
        
        # Test Case 3: Valid Driving Licence in Reg No -> PASS
        res3 = validate_east_zone_old_vehicle("MA1UV2CVXT6E17381", "DL-0420110012345")
        self.assertEqual(res3["east_zone_validation"], "PASS")
        self.assertEqual(res3["detected_document_type"], "DRIVING_LICENSE")
        self.assertEqual(res3["detected_value"], "DL-0420110012345")
        self.assertIn("Valid Driving Licence found in Reg No", res3["validation_reason"])
        
        # Test Case 4: Unreadable Chassis No -> HOLD
        res4 = validate_east_zone_old_vehicle("-", "UP16AB1234")
        self.assertEqual(res4["east_zone_validation"], "HOLD")
        self.assertEqual(res4["detected_document_type"], "UNKNOWN")
        self.assertEqual(res4["detected_value"], "")
        self.assertEqual(res4["validation_reason"], "Unable to verify PAN or Driving Licence")

        # Test Case 5: Unreadable Reg No -> HOLD
        res5 = validate_east_zone_old_vehicle("MA1UV2CVXT6E17381", "not found")
        self.assertEqual(res5["east_zone_validation"], "HOLD")
        self.assertEqual(res5["detected_document_type"], "UNKNOWN")
        self.assertEqual(res5["detected_value"], "")
        self.assertEqual(res5["validation_reason"], "Unable to verify PAN or Driving Licence")

        # Test Case 6: Cross-document validation matching PAN
        pan_doc = "This is a PAN document. PAN Number = BNTPK4567R. Name: John Doe."
        res6 = validate_east_zone_old_vehicle("BNTPK4567R", "-", pan_doc, "")
        self.assertEqual(res6["status"], "PASS")
        self.assertEqual(res6["matched_document"], "PAN")
        self.assertEqual(res6["matched_value"], "BNTPK4567R")
        self.assertIn("PAN matched with portal", res6["reason"])

        # Test Case 7: Cross-document validation matching DL
        dl_doc = "DRIVING LICENCE. DL No: UP-14 2023 0012345. DOB: 01/01/1990."
        res7 = validate_east_zone_old_vehicle("-", "UP1420230012345", "", dl_doc)
        self.assertEqual(res7["status"], "PASS")
        self.assertEqual(res7["matched_document"], "DRIVING_LICENSE")
        self.assertEqual(res7["matched_value"], "UP1420230012345")
        self.assertIn("Driving Licence matched", res7["reason"])

        # Test Case 8: Cross-document validation mismatch
        res8 = validate_east_zone_old_vehicle("MA1UV2CVXT6E17381", "UP16AB1234", pan_doc, dl_doc)
        self.assertEqual(res8["status"], "HOLD")
        self.assertIn("Portal values not matching", res8["reason"])

        # Test Case 9: Cross-document validation unable to read documents
        res9 = validate_east_zone_old_vehicle("BNTPK4567R", "-", "unreadable text", "unreadable text")
        self.assertEqual(res9["status"], "HOLD")
        self.assertIn("Unable to read PAN or Driving Licence number", res9["reason"])

    @patch("automate_login.verify_invoice_stamp_and_signatures")
    def test_validate_disclaimer_doc_city_matching(self, mock_sig):
        from automate_login import validate_disclaimer_doc
        mock_sig.return_value = (True, "GOOD", True, "GOOD")

        text = "CUSTOMER DISCLAIMER CONFIRM WELCOME DEALER VEHICLE CHASSIS ENGINE INVOICE"
        # Check when the city in claim_details is "KOLKATA" and the Welcome Bonus Amount in document is 30000.
        data = {
            "Customer Name": "Lancy Babu",
            "Registration No": "DL9CJ2283",
            "Vehicle Make": "Mahindra",
            "Vehicle Model": "VEERO",
            "New Vehicle Model": "VEERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026",
            "Disclaimer Date": "19/05/2026",
            "Welcome Bonus Amount": "30000"
        }
        validations = {"Name Match Status": "MATCH", "Name Match Score": 100.0}
        claim_details = {
            "New vehicle Model Group": "VEERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026",
            "Area Office": "KOLKATA AO"
        }
        issues = []
        
        with patch("automate_login.load_contribution_data") as mock_load:
            mock_load.return_value = {
                "welcome": {
                    "VEERO": [
                        {"city": "COMMON", "amount": 15000.0},
                        {"city": "KOLKATA", "amount": 30000.0}
                    ]
                },
                "scrappage": {}
            }
            validate_disclaimer_doc(
                filename="disclaimer.pdf",
                pdf_path="/mock/dir/disclaimer.pdf",
                text=text,
                data=data,
                validations=validations,
                claim_details=claim_details,
                old_vehicle_details=None,
                claim_choice=1,
                dashboard_scheme_type="welcome",
                company_name="Mahindra",
                customer_name="Lancy Babu",
                issues=issues
            )
        self.assertEqual(len(issues), 0)

        # Patna AO should fall back to COMMON (15000) and thus trigger a mismatch with doc amount (30000)
        claim_details_patna = {
            "New vehicle Model Group": "VEERO",
            "Chassis No": "COD20260590DL9CJ2283",
            "Invoice No": "INV-123",
            "Invoice Date": "19/05/2026",
            "Area Office": "PATNA AO"
        }
        issues2 = []
        with patch("automate_login.load_contribution_data") as mock_load:
            mock_load.return_value = {
                "welcome": {
                    "VEERO": [
                        {"city": "COMMON", "amount": 15000.0},
                        {"city": "KOLKATA", "amount": 30000.0}
                    ]
                },
                "scrappage": {}
            }
            validate_disclaimer_doc(
                filename="disclaimer.pdf",
                pdf_path="/mock/dir/disclaimer.pdf",
                text=text,
                data=data,
                validations=validations,
                claim_details=claim_details_patna,
                old_vehicle_details=None,
                claim_choice=1,
                dashboard_scheme_type="welcome",
                company_name="Mahindra",
                customer_name="Lancy Babu",
                issues=issues2
            )
        self.assertTrue(any("mismatch" in iss or "mismatches" in iss for iss in issues2))

    def test_chassis_suffix_ocr_matching(self):
        from automate_login import compare_values_robust
        
        # Scenario 1: Exact suffix match
        status1, score1 = compare_values_robust("MA1UV2CVXT6D14922", "T6D14922")
        self.assertTrue(status1.startswith("MATCH"))
        
        # Scenario 2: Suffix match with OCR insertion error ('K' inserted after 'T')
        status2, score2 = compare_values_robust("MA1UV2CVXTK6D14922", "T6D14922")
        self.assertTrue(status2.startswith("MATCH"))
        
        # Scenario 3: Mismatch where last digit is different
        status3, score3 = compare_values_robust("MA1UV2CVXTK6D14922", "T6D14923")
        self.assertFalse(status3.startswith("MATCH"))

if __name__ == "__main__":
    unittest.main()

