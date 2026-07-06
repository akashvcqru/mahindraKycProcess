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
_OEM_KEYWORDS     = ("CERTIFICATE OF DEPOSIT", "SCRAPPAGE CERTIFICATE", "COD", "OEM", "VAHAN SCREEN", "VAHAN", "SCREENSHOT", "SCREEN SHORT")
_DISCLAIMER_PREFIXES = ("DIS", "DSC", "CD-")
_DISCLAIMER_KEYWORDS = ("DISCLAIMER",)


def _is_ledger(filename):
    fn = filename.upper()
    if any(k in fn for k in ("LEDGER", "STMT", "STATEMENT")):
        return True
    prefixes = ("LDGR", "LES", "LGR", "LDR", "LDG")
    if any(fn.startswith(p) or f" {p}" in fn or f"-{p}" in fn for p in prefixes):
        return True
    if "-L-" in fn or " L-" in fn or fn.startswith("L-") or "-TL-" in fn or " TL-" in fn or fn.startswith("TL-"):
        return True
    return False


def _is_invoice(filename):
    fn = filename.upper()
    if any(k in fn for k in ("INVOICE", "TAX INV", "GST INV")):
        return True
    prefixes = ("INV",)
    if any(fn.startswith(p) or f" {p}" in fn or f"-{p}" in fn for p in prefixes):
        return True
    return False


def _is_cod(filename):
    fn = filename.upper()
    return (
        fn.startswith("COD")
        or "CERTIFICATE OF DEPOSIT" in fn
        or "COD" in fn
    )


def _is_oem(filename):
    fn = filename.upper()
    if any(k in fn for k in _OEM_KEYWORDS):
        return True
    if any(fn.startswith(p) or f" {p}" in fn or f"-{p}" in fn for p in _OEM_PREFIXES):
        return True
    return False


def _is_disclaimer(filename):
    fn = filename.upper()
    if "DISCLAIMER" in fn:
        return True
    prefixes = ("DIS", "DSC", "CD-")
    if any(fn.startswith(p) or f" {p}" in fn or f"-{p}" in fn for p in prefixes):
        return True
    return False


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

        # ── Ledger ───────────────────────────────────────────────────────────
        if _is_ledger(filename):
            found_ledger = True
            processed_files.add(f_path)
            logging.info(f"Passing Ledger to Scrappage Vision Extractor: {f_path}")
            success, msg = validate_ledger(f_path, claim_details, data_store)
            if not success:
                issues.append(f"Ledger Validation Failed: {msg}")

        # ── Invoice ──────────────────────────────────────────────────────────
        elif _is_invoice(filename):
            found_invoice = True
            processed_files.add(f_path)
            logging.info(f"Passing Invoice to Scrappage Invoice Validator: {f_path}")
            success, msg = validate_invoice(f_path, claim_details, data_store)
            if not success:
                issues.append(f"Invoice Validation Failed: {msg}")

        # ── COD Document ─────────────────────────────────────────────────────
        elif _is_cod(filename):
            found_oem = True
            processed_files.add(f_path)
            logging.info(f"Passing COD Document to Scrappage COD Validator: {f_path}")
            success, msg = validate_cod(f_path, claim_details, old_vehicle_details, data_store)
            if not success:
                issues.append(f"COD Document Validation Failed: {msg}")

        # ── OEM Document ─────────────────────────────────────────────────────
        elif _is_oem(filename):
            found_oem = True
            processed_files.add(f_path)
            logging.info(f"Passing OEM Document to Scrappage OEM Validator: {f_path}")
            success, msg = validate_oem(f_path, claim_details, old_vehicle_details, data_store)
            if not success:
                issues.append(f"OEM Document Validation Failed: {msg}")

        # ── Disclaimer ───────────────────────────────────────────────────────
        elif _is_disclaimer(filename):
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
                    if "CERTIFICATE DEPOSIT" in text or "CERTIFICATE OF DEPOSIT" in text or "COD" in text:
                        found_oem = True
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
