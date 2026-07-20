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
    """Centralized document classifier wrapper for Scrappage Scheme."""
    from document_processing.classifier import classify_document as _classify_document
    result = _classify_document(f_path)
    doc_type = result.get("type")
    confidence = result.get("confidence", 0.0)
    # Only return types relevant to scrappage_scheme
    if doc_type in ("INVOICE", "LEDGER", "DISCLAIMER", "COD", "OEM"):
        return doc_type
    # Low confidence fallback logic
    if confidence < 0.50:
        logging.warning(f"[scrappage processor] Could not classify {os.path.basename(f_path)} (conf={confidence:.2f})")
        return None
    return doc_type
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

                    has_oem_keywords = any(k in clean_text for k in ["OEM SCRAPPING", "OEM INCENTIVE", "DETAILS OF CDS", "VAHAN"])
                    has_cod_keywords = any(k in clean_text for k in ["CERTIFICATE DEPOSIT", "CERTIFICATE OF DEPOSIT", "COD"])

                    if has_oem_keywords or has_cod_keywords:
                        found_oem = True
                        if has_oem_keywords:
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
