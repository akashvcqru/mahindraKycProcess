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

# Keywords/prefixes for document classification
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
    filename = os.path.basename(f_path).upper()
    
    # ── 1. Filename prefix/keyword checks ──
    if "TAX INVOICE" in filename or "GST INVOICE" in filename or "INVOICE" in filename:
        return "INVOICE"
    for p in _INVOICE_PREFIXES:
        if filename.startswith(p) or f" {p}" in filename or f"-{p}" in filename or f"_{p}" in filename:
            return "INVOICE"

    if any(k in filename for k in ("LEDGER", "STMT", "STATEMENT")):
        return "LEDGER"
    for p in _LEDGER_PREFIXES:
        if filename.startswith(p) or f" {p}" in filename or f"-{p}" in filename or f"_{p}" in filename:
            return "LEDGER"

    if "DISCLAIMER" in filename or "DESCLAIMER" in filename:
        return "DISCLAIMER"
    for p in _DISCLAIMER_PREFIXES:
        if filename.startswith(p) or f" {p}" in filename or f"-{p}" in filename or f"_{p}" in filename:
            return "DISCLAIMER"

    # ── 2. Content fallback checks ──
    text = get_pdf_text(f_path).upper()
    if "CUSTOMER DISCLAIMER" in text or "DISCLAIMER FOR WELCOME" in text or "DISCLAIMER" in text or "DESCLAIMER" in text:
        return "DISCLAIMER"
    if "STATEMENT OF ACCOUNT" in text or "LEDGER" in text or "JOURNAL ENTRY" in text:
        return "LEDGER"
    if "TAX INVOICE" in text or "INVOICE" in text:
        return "INVOICE"
        
    return None

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
            ui_validations = {
                "Ledger Heading Classification": "PASS" if any(k in ext.get("document_type", {}).get("text", "").upper() for k in ("LEDGER", "STATEMENT", "ACCOUNT", "STMT")) else "FAIL",
                "Customer Name Verification": "MATCH" if "Customer Name mismatch" not in msg else "MISMATCH",
                "Dealership Name Verification": "MATCH" if "Dealership Name mismatch" not in msg else "MISMATCH",
                "Welcome Bonus Amount Verification": "MATCH" if "Amount mismatch" not in msg else "MISMATCH",
                "Dealership Stamp/Seal Presence": "FOUND" if "stamp/seal is missing" not in msg else "MISSING",
                "Stamp Authorized Signature": "FOUND" if "authorized signature is missing" not in msg else "MISSING"
            }

        # ── Invoice ──────────────────────────────────────────────────────────
        elif doc_type == "INVOICE":
            found_invoice = True
            success, msg = validate_invoice(f_path, claim_details, data_store)
            if not success:
                issues.append(f"Invoice Validation Failed: {msg}")
            
            ext = data_store.get_doc_data("invoice")
            ui_extracted = {k: v.get("text") for k, v in ext.items() if isinstance(v, dict)}
            ui_validations = {
                "Invoice Classification": "PASS" if "INVOICE" in ext.get("document_type", {}).get("text", "").upper() else "FAIL",
                "Chassis Number Verification": "MATCH" if "Chassis Number mismatch" not in msg and "Chassis Number not found" not in msg else "MISMATCH",
                "Invoice Number Verification": "MATCH" if "Invoice Number mismatch" not in msg else "MISMATCH",
                "Invoice Date Verification": "MATCH" if "Invoice Date mismatch" not in msg else "MISMATCH",
                "Customer Name Verification": "MATCH" if "Customer Name mismatch" not in msg else "MISMATCH",
                "Dealership Name Verification": "MATCH" if "Dealership Name mismatch" not in msg else "MISMATCH",
                "New Vehicle Model Verification": "MATCH" if "Vehicle Model mismatch" not in msg else "MISMATCH",
                "Customer Signature Presence": "FOUND" if "Customer signature is missing" not in msg else "MISSING",
                "Dealership Stamp/Seal Presence": "FOUND" if "stamp/seal is missing" not in msg else "MISSING",
                "Stamp Authorized Signature": "FOUND" if "authorized signature is missing" not in msg else "MISSING"
            }

        # ── Disclaimer ───────────────────────────────────────────────────────
        elif doc_type == "DISCLAIMER":
            found_disclaimer = True
            success, msg = validate_disclaimer(f_path, claim_details, old_vehicle_details, data_store)
            if not success:
                issues.append(f"Disclaimer Validation Failed: {msg}")
            
            ext = data_store.get_doc_data("disclaimer")
            ui_extracted = {k: v.get("text") for k, v in ext.items() if isinstance(v, dict)}
            ui_validations = {
                "Disclaimer Heading Classification": "PASS" if "DISCLAIMER" in ext.get("document_title", {}).get("text", "").upper() else "FAIL",
                "Chassis Number Verification": "MATCH" if "Chassis Number mismatch" not in msg and "Chassis Number not found" not in msg else "MISMATCH",
                "Invoice Number Verification": "MATCH" if "Invoice Number mismatch" not in msg else "MISMATCH",
                "Invoice Date Verification": "MATCH" if "Invoice Date mismatch" not in msg else "MISMATCH",
                "Date Progression (Invoice <= Disclaimer)": "PASS" if "cannot be after" not in msg else "FAIL",
                "Customer Name Verification": "MATCH" if "Customer Name mismatch" not in msg else "MISMATCH",
                "Dealership Name Verification": "MATCH" if "Dealership Name mismatch" not in msg else "MISMATCH",
                "New Vehicle Model Verification": "MATCH" if "Vehicle Model mismatch" not in msg else "MISMATCH",
                "Welcome Bonus Amount Verification": "MATCH" if "Amount mismatch" not in msg else "MISMATCH",
                "Customer Signature Presence": "FOUND" if "Customer signature is missing" not in msg else "MISSING",
                "Dealership Stamp/Seal Presence": "FOUND" if "stamp/seal is missing" not in msg else "MISSING",
                "Stamp Authorized Signature": "FOUND" if "authorized signature is missing" not in msg else "MISSING"
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
