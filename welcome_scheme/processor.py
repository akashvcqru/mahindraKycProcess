import logging
import os
import glob
import re
import sys
from .data_store import WelcomeDataStore
from .ledger_validation import validate_ledger
from .invoice_validation import validate_invoice
from .disclaimer_validation import validate_disclaimer
from .relational_document_validation import validate_relational
from document_processing.classifier import classify_document as _classify_document

# Keywords/prefixes for document classification (kept for legacy processor.get_pdf_text)
_LEDGER_PREFIXES  = ("LDGR", "LES", "L-", "LGR", "LDR", "LDG")
_LEDGER_KEYWORDS  = ("LEDGER",)
_INVOICE_PREFIXES = ("INV",)
_INVOICE_KEYWORDS = ("INVOICE", "TAX INV", "GST INV")
_DISCLAIMER_PREFIXES = ("DIS", "DSC", "CD-", "DS", "MFC", "FC", "CERT", "FORM", "CUST", "DECL", "DIC", "DEC")
_DISCLAIMER_KEYWORDS = ("DISCLAIMER",)

def get_am():
    return sys.modules.get("automate_login") or __import__("automate_login")

def get_pdf_text(f_path):
    # Check if a cached OCR file exists in scratch/ocr_txt
    try:
        parent = os.path.basename(os.path.dirname(f_path))
        fname = os.path.basename(f_path)
        cache_path = os.path.join("scratch", "ocr_txt", f"{parent}_{fname}.txt")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_text = f.read()
            if len(cached_text.strip()) >= 10:
                logging.info(f"[processor] Loaded OCR text from cache: {cache_path}")
                return cached_text
    except Exception as cache_err:
        logging.warning(f"[processor] Cache lookup failed: {cache_err}")

    import fitz
    text = ""
    try:
        doc = fitz.open(f_path)
        text = "".join(page.get_text() for page in doc)
        if len(text.strip()) < 10:
            logging.info(f"PDF {f_path} has no embedded text. Running fallback OCR for classification...")
            try:
                import easyocr
                import numpy as np
                from PIL import Image
                import io
                
                reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                pix = doc[0].get_pixmap(dpi=150)
                png_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
                img_array = np.array(pil_img)
                
                ocr_results = reader.readtext(img_array, detail=0)
                text = " ".join(ocr_results)
            except Exception as ocr_err:
                logging.warning(f"OCR failed for {f_path} during classification: {ocr_err}")
    except Exception as e:
        logging.error(f"Error reading PDF {f_path}: {e}")
    return text

def classify_document(f_path):
    """Thin wrapper around the new centralized document classifier."""
    result = _classify_document(f_path)
    doc_type = result.get("type")
    confidence = result.get("confidence", 0.0)
    # Only return types relevant to welcome_scheme
    if doc_type in ("INVOICE", "LEDGER", "DISCLAIMER"):
        return doc_type
    # Low confidence = log as unknown
    if confidence < 0.50:
        logging.warning(f"[processor] Could not classify {os.path.basename(f_path)} (conf={confidence:.2f})")
        return None
    return doc_type

def process_welcome(
    target_dir,
    customer_name,
    claim_details=None,
    old_vehicle_details=None,
    claim_choice=None,
    dashboard_dealer_name=None,
    dashboard_scheme_type=None
):
    """
    Main entry point for processing a Welcome Bonus claim row.
    Returns a list of issue strings — empty means APPROVED.
    """
    if claim_details is None:
        claim_details = {}
    if old_vehicle_details is None:
        old_vehicle_details = {}

    if dashboard_dealer_name and "Dealer Name" not in claim_details:
        claim_details["Dealer Name"] = dashboard_dealer_name
    if dashboard_scheme_type and "Scheme" not in claim_details:
        claim_details["Scheme"] = dashboard_scheme_type

    logging.info(f"--- Starting Welcome Bonus Scheme Processing for {customer_name} ---")

    # Initialize Data Store
    store_path = os.path.join(
        "scratch", f"welcome_store_{customer_name.replace(' ', '_')}.json"
    )
    data_store = WelcomeDataStore(storage_path=store_path)

    issues = []
    found_ledger  = False
    found_invoice = False
    found_disclaimer = False

    # Collect downloaded files
    pdf_files = []
    if os.path.exists(target_dir):
        for ext in ["*.pdf", "*.jpg", "*.jpeg", "*.png", "*.img"]:
            pdf_files.extend(glob.glob(os.path.join(target_dir, ext)))
            pdf_files.extend(glob.glob(os.path.join(target_dir, ext.upper())))
        pdf_files = list(dict.fromkeys(pdf_files))
        logging.info(
            f"Welcome Bonus Processor found {len(pdf_files)} documents in {target_dir}"
        )
    else:
        logging.warning(f"Target directory does not exist: {target_dir}")

    am = get_am()

    for f_path in pdf_files:
        filename = os.path.basename(f_path)
        doc_type = classify_document(f_path)
        logging.info(f"Document {filename} classified as: {doc_type}")

        ui_extracted = {}
        ui_validations = {}
        msg = ""

        # ── Ledger ───────────────────────────────────────────────────────────
        if doc_type == "LEDGER":
            found_ledger = True
            success, msg = validate_ledger(f_path, claim_details, data_store)
            if not success:
                issues.append(f"Ledger Validation Failed: {msg}")
            
            ext = data_store.get_doc_data("ledger")
            ui_extracted = {k: v.get("text") for k, v in ext.items() if isinstance(v, dict)}

            def _conf_status(key, pass_str="PASS", fail_str="FAIL"):
                """Return PASS/FAIL/UNKNOWN based on field confidence."""
                field = ext.get(key, {})
                if isinstance(field, dict):
                    conf = field.get("confidence", 1.0)
                    if conf < 0.60:
                        return "UNKNOWN"
                return pass_str

            ui_validations = {
                "Ledger Heading Classification": "PASS" if any(k in ext.get("document_type", {}).get("text", "").upper() for k in ("LEDGER", "STATEMENT", "ACCOUNT", "STMT")) else "FAIL",
                "Customer Name Verification": "UNKNOWN" if _conf_status("customer_name") == "UNKNOWN" else ("PASS" if "Customer Name mismatch" not in msg else "FAIL"),
                "Dealership Name Verification": "UNKNOWN" if _conf_status("dealership_name") == "UNKNOWN" else ("PASS" if "Dealership Name mismatch" not in msg else "FAIL"),
                "Welcome Bonus Amount Verification": "PASS" if "Amount mismatch" not in msg else "FAIL",
                "Dealership Stamp/Seal Presence": "UNKNOWN" if "stamp/seal is missing" not in msg and ext.get("dealer_stamp", {}).get("confidence", 1.0) < 0.60 else ("PASS" if "stamp/seal is missing" not in msg else "FAIL"),
                "Stamp Authorized Signature": "PASS" if "authorized signature is missing" not in msg else "FAIL"
            }

        # ── Invoice ──────────────────────────────────────────────────────────
        elif doc_type == "INVOICE":
            found_invoice = True
            success, msg = validate_invoice(f_path, claim_details, data_store)
            if not success:
                issues.append(f"Invoice Validation Failed: {msg}")
            
            ext = data_store.get_doc_data("invoice")
            ui_extracted = {k: v.get("text") for k, v in ext.items() if isinstance(v, dict)}

            def _inv_conf_status(key):
                field = ext.get(key, {})
                if isinstance(field, dict) and field.get("confidence", 1.0) < 0.60:
                    return "UNKNOWN"
                return None

            ui_validations = {
                "Invoice Classification": "PASS" if "INVOICE" in ext.get("document_type", {}).get("text", "").upper() else "FAIL",
                "Chassis Number Verification": _inv_conf_status("chassis_number") or ("PASS" if "Chassis Number mismatch" not in msg and "Chassis Number not found" not in msg else "FAIL"),
                "Invoice Number Verification": _inv_conf_status("invoice_number") or ("PASS" if "Invoice Number mismatch" not in msg else "FAIL"),
                "Invoice Date Verification": _inv_conf_status("invoice_date") or ("PASS" if "Invoice Date mismatch" not in msg else "FAIL"),
                "Customer Name Verification": _inv_conf_status("customer_name") or ("PASS" if "Customer Name mismatch" not in msg else "FAIL"),
                "Dealership Name Verification": _inv_conf_status("dealership_name") or ("PASS" if "Dealership Name mismatch" not in msg else "FAIL"),
                "New Vehicle Model Verification": _inv_conf_status("new_vehicle_model") or ("PASS" if "Vehicle Model mismatch" not in msg else "FAIL"),
                "Customer Signature Presence": "UNKNOWN" if ext.get("customer_signature", {}).get("confidence", 1.0) < 0.35 else ("PASS" if "Customer signature is missing" not in msg else "FAIL"),
                "Dealership Stamp/Seal Presence": "UNKNOWN" if ext.get("dealer_stamp", {}).get("confidence", 1.0) < 0.35 else ("PASS" if "stamp/seal is missing" not in msg else "FAIL"),
                "Stamp Authorized Signature": "PASS" if "authorized signature is missing" not in msg else "FAIL"
            }

        # ── Disclaimer ───────────────────────────────────────────────────────
        elif doc_type == "DISCLAIMER":
            found_disclaimer = True
            success, msg = validate_disclaimer(f_path, claim_details, old_vehicle_details, data_store)
            if not success:
                issues.append(f"Disclaimer Validation Failed: {msg}")
            
            ext = data_store.get_doc_data("disclaimer")
            ui_extracted = {k: v.get("text") for k, v in ext.items() if isinstance(v, dict)}

            def _disc_conf_status(key):
                field = ext.get(key, {})
                if isinstance(field, dict) and field.get("confidence", 1.0) < 0.60:
                    return "UNKNOWN"
                return None

            ui_validations = {
                "Disclaimer Heading Classification": "PASS" if "DISCLAIMER" in ext.get("document_title", {}).get("text", "").upper() else "FAIL",
                "Chassis Number Verification": _disc_conf_status("chassis_number") or ("PASS" if "Chassis Number mismatch" not in msg and "Chassis Number not found" not in msg else "FAIL"),
                "Invoice Number Verification": _disc_conf_status("invoice_number") or ("PASS" if "Invoice Number mismatch" not in msg else "FAIL"),
                "Invoice Date Verification": _disc_conf_status("invoice_date") or ("PASS" if "Invoice Date mismatch" not in msg else "FAIL"),
                "Date Progression (Invoice <= Disclaimer)": "PASS" if "cannot be after" not in msg else "FAIL",
                "Customer Name Verification": _disc_conf_status("customer_name") or ("PASS" if "Customer Name mismatch" not in msg else "FAIL"),
                "Dealership Name Verification": _disc_conf_status("dealership_name") or ("PASS" if "Dealership Name mismatch" not in msg else "FAIL"),
                "New Vehicle Model Verification": _disc_conf_status("model") or ("PASS" if "Vehicle Model mismatch" not in msg else "FAIL"),
                "Welcome Bonus Amount Verification": "PASS" if "Amount mismatch" not in msg else "FAIL",
                "Customer Signature Presence": "UNKNOWN" if ext.get("customer_signature", {}).get("confidence", 1.0) < 0.35 else ("PASS" if "Customer signature is missing" not in msg else "FAIL"),
                "Dealership Stamp/Seal Presence": "UNKNOWN" if ext.get("dealer_stamp", {}).get("confidence", 1.0) < 0.35 else ("PASS" if "stamp/seal is missing" not in msg else "FAIL"),
                "Stamp Authorized Signature": "PASS" if "authorized signature is missing" not in msg else "FAIL"
            }

        # Update GUI elements with extracted metadata
        if doc_type in ("LEDGER", "INVOICE", "DISCLAIMER"):
            for doc in am.CURRENT_ROW_DOCUMENTS:
                if os.path.abspath(doc["file_path"]) == os.path.abspath(f_path):
                    doc["extracted_data"] = ui_extracted
                    doc["validations"] = ui_validations
                    doc["file_type"] = doc_type

    # Missing document checks
    if not found_ledger:
        issues.append("Missing Ledger Document")
    if not found_invoice:
        issues.append("Missing Invoice Document")
    if not found_disclaimer:
        issues.append("Missing Disclaimer Document")

    return issues
