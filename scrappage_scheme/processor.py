import logging
import os
import glob
from .data_store import ScrappageDataStore
from .ledger_validation import validate_ledger
from .invoice_validation import validate_invoice
from .oem_document_validation import validate_oem
from .disclaimer_validation import validate_disclaimer
from .cod_validation import validate_cod

# Prefixes / keywords that identify each document type from the portal filename
_LEDGER_PREFIXES  = ("LDGR", "LES", "L-", "LGR", "LDR", "LDG")
_LEDGER_KEYWORDS  = ("LEDGER",)
_INVOICE_PREFIXES = ("INV",)
_INVOICE_KEYWORDS = ("INVOICE", "TAX INV", "GST INV")
_OEM_PREFIXES     = ("COD", "OEM")
_OEM_KEYWORDS     = ("CERTIFICATE OF DEPOSIT", "CERTIFICATE DEPOSIT", "SCRAPPAGE CERTIFICATE", "COD", "OEM", "VAHAN SCREEN", "VAHAN", "SCREENSHOT", "SCREEN SHORT", "OEM SCRAPPING", "OEM SCRAPPING INCENTIVE")
_DISCLAIMER_PREFIXES = ("DIS", "DSC", "CD-", "DS")
_DISCLAIMER_KEYWORDS = ("DISCLAIMER",)


def classify_document(f_path):
    from .cod_validation import get_pdf_text
    
    filename = os.path.basename(f_path).upper()
    
    # Try content text/OCR check
    text = ""
    try:
        text = get_pdf_text(f_path).upper()
    except Exception as exc:
        logging.warning(f"Could not extract text for classification of {f_path}: {exc}")

    # 1. COD (High specificity check)
    if "TRANSFER CERTIFICATE OF DEPOSIT" in text:
        return "COD"

    # 2. OEM (High specificity check)
    if "OEM SCRAPPING" in text or "OEM INCENTIVE" in text or "VAHAN" in text or "SCRAPPAGE CERTIFICATE" in text:
        return "OEM"

    # 3. Disclaimer (High specificity check)
    if "DISCLAIMER" in text or "DESCLAIMER" in text:
        return "DISCLAIMER"

    # 4. COD (Lower specificity fallback)
    if "CERTIFICATE OF DEPOSIT" in text or "CERTIFICATE DEPOSIT" in text:
        return "COD"

    # 5. Invoice
    if "TAX INVOICE" in text or "GST INVOICE" in text or "INVOICE" in text or "INVOLCE" in text:
        return "INVOICE"

    # 6. Ledger
    if "LEDGER" in text or "STATEMENT OF ACCOUNT" in text or "STMT OF" in text:
        return "LEDGER"

    # ── Filename Fallback ────────────────────────────────────────────────────
    if "DISCLAIMER" in filename or "DESCLAIMER" in filename:
        return "DISCLAIMER"
    for p in ("DIS", "DSC", "CD-", "DES", "DS"):
        if filename.startswith(p) or f" {p}" in filename or f"-{p}" in filename:
            return "DISCLAIMER"

    if "TRANSFER CERTIFICATE OF DEPOSIT" in filename or "CERTIFICATE OF DEPOSIT" in filename or "COD" in filename:
        return "COD"

    for k in ("INVOICE", "TAX INV", "GST INV"):
        if k in filename:
            return "INVOICE"
    for p in ("INV",):
        if filename.startswith(p) or f" {p}" in filename or f"-{p}" in filename:
            return "INVOICE"

    if any(k in filename for k in ("LEDGER", "STMT", "STATEMENT")):
        return "LEDGER"
    for p in ("LDGR", "LES", "LGR", "LDR", "LDG", "LED", "L-"):
        if filename.startswith(p) or f" {p}" in filename or f"-{p}" in filename:
            return "LEDGER"

    for k in ("CERTIFICATE OF DEPOSIT", "CERTIFICATE DEPOSIT", "SCRAPPAGE CERTIFICATE", "COD", "OEM", "VAHAN SCREEN", "VAHAN", "SCREENSHOT", "SCREEN SHORT", "OEM SCRAPPING", "OEM SCRAPPING INCENTIVE"):
        if k in filename:
            return "OEM"
    for p in ("COD", "OEM"):
        if filename.startswith(p) or f" {p}" in filename or f"-{p}" in filename:
            return "OEM"

    return None


def process_scrappage(claim_details, old_vehicle_details, target_dir):
    """
    Main entry point for processing a Scrappage Scheme claim row.
    Returns a list of issue strings — empty means APPROVED.
    """
    customer_name = claim_details.get("Customer Name", "Unknown")
    logging.info(f"--- Starting Scrappage Scheme Processing for {customer_name} ---")

    # Initialize Data Store for this specific customer/claim
    store_path = os.path.join(
        "scratch", f"scrappage_store_{customer_name.replace(' ', '_')}.json"
    )
    data_store = ScrappageDataStore(storage_path=store_path)

    issues = []
    found_ledger  = False
    found_invoice = False
    found_oem     = False
    found_disclaimer = False

    # Collect all downloaded files
    pdf_files = []
    if os.path.exists(target_dir):
        for ext in ["*.pdf", "*.jpg", "*.jpeg", "*.png", "*.img"]:
            pdf_files.extend(glob.glob(os.path.join(target_dir, ext)))
            pdf_files.extend(glob.glob(os.path.join(target_dir, ext.upper())))
        pdf_files = list(dict.fromkeys(pdf_files))
        logging.info(
            f"Scrappage Processor found {len(pdf_files)} documents in {target_dir}"
        )
    else:
        logging.warning(f"Target directory does not exist: {target_dir}")

    processed_files = set()
    for f_path in pdf_files:
        filename = os.path.basename(f_path)
        doc_type = classify_document(f_path)
        logging.info(f"Document {filename} classified as: {doc_type}")

        # ── Ledger ───────────────────────────────────────────────────────────
        if doc_type == "LEDGER":
            found_ledger = True
            processed_files.add(f_path)
            logging.info(f"Passing Ledger to Scrappage Vision Extractor: {f_path}")
            success, msg = validate_ledger(f_path, claim_details, data_store)
            if not success:
                issues.append(f"Ledger Validation Failed: {msg}")

        # ── Invoice ──────────────────────────────────────────────────────────
        elif doc_type == "INVOICE":
            found_invoice = True
            processed_files.add(f_path)
            logging.info(f"Passing Invoice to Scrappage Invoice Validator: {f_path}")
            success, msg = validate_invoice(f_path, claim_details, data_store)
            if not success:
                issues.append(f"Invoice Validation Failed: {msg}")

        # ── COD Document ─────────────────────────────────────────────────────
        elif doc_type == "COD":
            found_oem = True
            processed_files.add(f_path)
            logging.info(f"Passing COD Document to Scrappage COD Validator: {f_path}")
            success, msg = validate_cod(f_path, claim_details, old_vehicle_details, data_store)
            if not success:
                issues.append(f"COD Document Validation Failed: {msg}")

        # ── OEM Document ─────────────────────────────────────────────────────
        elif doc_type == "OEM":
            found_oem = True
            processed_files.add(f_path)
            logging.info(f"Passing OEM Document to Scrappage OEM Validator: {f_path}")
            success, msg = validate_oem(f_path, claim_details, old_vehicle_details, data_store)
            if not success:
                issues.append(f"OEM Document Validation Failed: {msg}")

        # ── Disclaimer ───────────────────────────────────────────────────────
        elif doc_type == "DISCLAIMER":
            found_disclaimer = True
            processed_files.add(f_path)
            logging.info(f"Passing Disclaimer to Scrappage Disclaimer Validator: {f_path}")
            success, msg = validate_disclaimer(f_path, claim_details, old_vehicle_details, data_store)
            if not success:
                issues.append(f"Disclaimer Validation Failed: {msg}")

    # ── Fallback: Check unmatched PDFs text for COD/OEM ───────────────────────
    if not found_oem:
        import fitz
        for f_path in pdf_files:
            if f_path in processed_files:
                continue
            try:
                doc = fitz.open(f_path)
                if len(doc) > 0:
                    text = doc[0].get_text().upper()
                    import re
                    clean_text = re.sub(r'\s+', ' ', text)
                    
                    if len(clean_text.strip()) < 10:
                        logging.info(f"PDF {f_path} has no embedded text. Attempting OCR fallback...")
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
                            ocr_text = " ".join(ocr_results).upper()
                            clean_text = re.sub(r'\s+', ' ', ocr_text)
                        except Exception as ocr_err:
                            logging.warning(f"OCR fallback failed for {f_path}: {ocr_err}")

                    if any(k in clean_text for k in ["CERTIFICATE DEPOSIT", "CERTIFICATE OF DEPOSIT", "COD", "OEM SCRAPPING"]):
                        found_oem = True
                        if "OEM SCRAPPING" in clean_text or ("CERTIFICATE DEPOSIT" in clean_text and "TRANSFER" not in clean_text):
                            logging.info(f"Fallback: Identified OEM document via text content: {f_path}")
                            success, msg = validate_oem(f_path, claim_details, old_vehicle_details, data_store)
                            if not success:
                                issues.append(f"OEM Document Validation Failed: {msg}")
                        else:
                            logging.info(f"Fallback: Identified COD document via text content: {f_path}")
                            success, msg = validate_cod(f_path, claim_details, old_vehicle_details, data_store)
                            if not success:
                                issues.append(f"COD Document Validation Failed: {msg}")
                        break
            except Exception as e:
                logging.warning(f"Fallback check failed for {f_path}: {e}")

    # ── Missing document checks ───────────────────────────────────────────────
    if not found_ledger:
        issues.append("Missing Ledger Document")
    if not found_invoice:
        issues.append("Missing Invoice Document")
    if not found_oem:
        issues.append("Missing Certificate of Deposit (COD/OEM) Document")
    if not found_disclaimer:
        issues.append("Missing Disclaimer Document")

    return issues
