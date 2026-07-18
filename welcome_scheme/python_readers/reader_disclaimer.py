"""
reader_disclaimer.py
====================
Python-native extractor for Welcome Bonus Disclaimer documents.
"""

import re
import logging
import os

from .reader_base import extract_pdf_text, is_text_based, _field, first_match, line_of


# ── Patterns ──────────────────────────────────────────────────────────────────

_DOC_TITLE = r"(Customer\s+Disclaimer)"

# Customer Name from declaration or labels
_CUST_DECL = r"(?:I|1|l|\|),\s*([^,]+?)\s*,\s*(?:residing|s/o|d/o|w/o|r/o|son|daughter|wife|do\s+hereby)"
_CUST_LABEL = r"(?:Customer\s+Name|Name\s+of\s+Customer)\s*[:\-]?\s*([A-Z][A-Z\s\.]+?)(?:\n|Contact|Declared|$)"
_CUST_PAREN = r"\(\s*([A-Z][A-Z\s]{4,30})\s*\)"

# Dates
_DATE_LABEL = r"(?:Date|Disclaimer\s+Date)\s*[:\-]\s*(\d{1,2}[\-/\.\s](?:[A-Za-z]{3,9}|\d{1,2})[\-/\.\s]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})"
_DATE_DECLARED = r"Declared\s+at\s+.*?\s+on\s+this\s+([0-9\s]+(?:of\s+)?[A-Za-z\s,]+202\d)"

# Welcome Bonus Amount
_WELCOME_AMOUNT = r"Welcome\s+Bonus\s+of\s+Rs\.?\s*(\d+)"
_WELCOME_AMOUNT_ALT = r"(?:Bonus|Benefit)\s+(?:of\s+)?(?:INR|Rs\.?)\s*([\d,]+(?:\.\d+)?)"

# New vehicle/Invoice details
_MODEL = r"(?:Model|Vehicle\s+Model)\s*[:\-]?\s*([A-Z0-9\s\-/\(\)]+?)(?:\n|Chassis|Engine|$)"
_CHASSIS = r"Chassis\s*(?:no|num|number)?\s*[:\-_]?\s*([A-Z0-9\s]{5,25}?)(?=\s*(?:Engine|Inv|Invoice|Date|Declared|$))"
_ENGINE = r"Engine\s*(?:no|num|number)?\s*[:\-_]?\s*([A-Z0-9\s]+?)(?=\s*(?:Inv|Invoice|Date|Declared|$))"
_INVOICE_NO = r"(?:Invoice_No|Invoice\s*No\.?|ice_No|Inv\s*No\.?|Invoice_No_)\s*[:\-_]?\s*([A-Z0-9/\-_]+)"
_INVOICE_DATE = r"Invoice\s+Date\s*[:\-_]?\s*(?:\n)?\s*(\d{1,2}[\-/\.][A-Za-z0-9]{2,4}[\-/\.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})"


def extract_fields_from_text(text: str) -> dict:
    lines = text.splitlines()
    result = {}

    # document_title
    val = first_match(_DOC_TITLE, text)
    if val:
        result["document_title"] = _field(val.strip(), line_of(_DOC_TITLE, lines))
    else:
        if "disclaimer" in text.lower():
            result["document_title"] = _field("Customer Disclaimer", 1)

    # dealership_name — try company-keyword lines first
    skip_kw = ("neither", "nor", "harmless", "indemnify", "representatives", "agents", "shall be held", "hereby", "basis above")
    for i, ln in enumerate(lines, 1):
        ln_strip = ln.strip()
        if len(ln_strip) < 6:
            continue
        if re.search(r"(PVT\.?\s*LTD|MOTORS|AUTO|ENTERPRISES|AGENCY|LTD\.?)\b", ln_strip, re.IGNORECASE):
            if any(k in ln_strip.lower() for k in skip_kw):
                continue
            result["dealership_name"] = _field(ln_strip, i)
            break

    # dealership_name — fallback: extract from embedded sentence "Dealership name_XYZ" or "from the Dealership name XYZ"
    if "dealership_name" not in result:
        for i, ln in enumerate(lines, 1):
            # Pattern: "Dealership name_NR Autos" or "Dealership name NR Autos"
            dm = re.search(r"Dealership\s+name[_\s]+([A-Za-z][A-Za-z0-9\s\.\&\(\)\/\-]+?)(?:\s+for\b|\s+Buy|\s+Model|\s*$)", ln, re.IGNORECASE)
            if dm:
                dealer_text = dm.group(1).strip().rstrip("_,")
                if len(dealer_text) >= 4:
                    result["dealership_name"] = _field(dealer_text, i)
                    break

    # customer_name
    val = first_match(_CUST_LABEL, text)
    if not val:
        val = first_match(_CUST_DECL, text)
    if not val:
        for ln in reversed(lines):
            m = re.search(_CUST_PAREN, ln)
            if m:
                cand = m.group(1).strip()
                if cand and not any(k in cand.upper() for k in ("WITNESS", "SIGNATURE", "DEALER", "AUTHORISED", "SHREE", "AUTOMOTIVE")):
                    val = cand
                    break
    if val:
        result["customer_name"] = _field(val.strip(), line_of(_CUST_LABEL, lines) or line_of(_CUST_DECL, lines) or 1)

    # disclaimer_date
    val = first_match(_DATE_LABEL, text)
    if not val:
        val = first_match(_DATE_DECLARED, text)
    if val:
        result["disclaimer_date"] = _field(val.strip(), line_of(_DATE_LABEL, lines) or line_of(_DATE_DECLARED, lines))

    # welcome_bonus_amount
    val = first_match(_WELCOME_AMOUNT, text)
    if not val:
        val = first_match(_WELCOME_AMOUNT_ALT, text)
    if val:
        result["welcome_bonus_amount"] = _field(val.strip().replace(",", ""), line_of(_WELCOME_AMOUNT, lines) or line_of(_WELCOME_AMOUNT_ALT, lines))

    # model
    val = first_match(_MODEL, text)
    if val:
        result["model"] = _field(val.strip(), line_of(_MODEL, lines))
    else:
        models = ["THAR ROXX", "THAR", "BOLERO PIKUP", "BOLERO", "SUPRO", "JAYO", "XUV3XO", "XUV", "SCORPIO", "VEERO", "EERO"]
        for m in models:
            if m in text.upper() or "SUPRQ" in text.upper():
                result["model"] = _field(m if m != "SUPRO" or "SUPRQ" not in text.upper() else "SUPRO", 1)
                break

    # chassis_number (strip spaces from extracted match)
    val = first_match(_CHASSIS, text)
    if val:
        clean_ch = re.sub(r"[^A-Z0-9]", "", val.upper())
        result["chassis_number"] = _field(clean_ch, line_of(_CHASSIS, lines))

    # engine_number (strip spaces)
    val = first_match(_ENGINE, text)
    if val:
        clean_eg = re.sub(r"[^A-Z0-9]", "", val.upper())
        result["engine_number"] = _field(clean_eg, line_of(_ENGINE, lines))

    # invoice_number
    val = first_match(_INVOICE_NO, text)
    if val:
        result["invoice_number"] = _field(val.strip(), line_of(_INVOICE_NO, lines))

    # invoice_date
    val = first_match(_INVOICE_DATE, text)
    if val:
        result["invoice_date"] = _field(val.strip(), line_of(_INVOICE_DATE, lines))

    return result


def try_extract_disclaimer_fields(pdf_path: str, claim_details: dict = None) -> dict | None:
    """
    Attempt to extract disclaimer fields using native PDF text or OCR if image-based.
    """
    from .reader_base import assist_extraction_with_portal
    text = extract_pdf_text(pdf_path)
    
    result = {}
    if len(text.strip()) >= 80:
        result = extract_fields_from_text(text)
        
    critical_fields = ["customer_name", "chassis_number"]
    has_critical = all(k in result for k in critical_fields)
    
    parent = os.path.basename(os.path.dirname(pdf_path))
    fname = os.path.basename(pdf_path)
    cache_path = os.path.join("scratch", "ocr_txt", f"{parent}_{fname}.txt")
    
    if (len(result) < 4 or not has_critical) and not os.path.exists(cache_path):
        logging.info(f"[reader_disclaimer] Text extraction insufficient. Running EasyOCR fallback for {pdf_path}...")
        try:
            import fitz
            import easyocr
            import numpy as np
            import io
            from PIL import Image
            doc = fitz.open(pdf_path)
            reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            ocr_lines = []
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                res = reader.readtext(np.array(img), detail=0)
                ocr_lines.extend(res)
            ocr_text = "\n".join(ocr_lines)
            
            ocr_result = extract_fields_from_text(ocr_text)
            if len(ocr_result) > len(result):
                result = ocr_result
            # Try combining them or applying portal assist to OCR text
            result = assist_extraction_with_portal(result, ocr_text, claim_details)
        except Exception as e:
            logging.error(f"[reader_disclaimer] OCR failed: {e}")
            
    # Apply portal assist on top of final results
    result = assist_extraction_with_portal(result, text, claim_details)
    found = list(result.keys())
    logging.info(f"[welcome reader_disclaimer] Final extracted fields: {found}")
    return result
