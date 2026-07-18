"""
reader_invoice.py
=================
Python-native extractor for Welcome Bonus Invoice documents.
"""

import re
import logging
import os

from .reader_base import extract_pdf_text, is_text_based, _field, first_match, line_of


# ── Patterns ──────────────────────────────────────────────────────────────────

_DOC_TYPE = r"(TAX\s+INVOI[COEA]|GST\s+INVOI[COEA]|GSL\s+lVOI[COEA]|RETAIL\s+INVOI[COEA]|INVOICE|VAX\s+INVO[IL]C[EA]|TAX\s+INVOLCE|INVOLCE)"

_INV_NO = r"(?:Invoice|Invoic[eo]|Bill|Inv)\s*(?:No|Number|_No|_No_)?\s*[:\-_;]?\s*(?:\n)?\s*([A-Z0-9][A-Z0-9/\-_]{4,})"
_INV_DATE = r"(?:Invoice\s+)?Date\s*[:\-]?\s*(\d{1,2}[\-\/\.](?:[A-Za-z]{3,9}|\d{1,2})[\-\/\.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})"

_CUST_NAME = (
    r"(?:Name\s+of\s+Buyer|Buyer(?:'s)?\s+Name|Customer\s+Name|Bill\s+To|Consignee)\s*[:\-]?\s*(?:\n)?\s*"
    r"([A-Z][A-Z\s\.]+?)(?:\n|GST|PAN|Addr|Mobile|Phone|$)"
)
_CUST_NAME_FALLBACK = r"(?:Buyer|Customer|Name)\s*[:\-]?\s*(?:\n)?\s*([A-Z][A-Z\s\.]+?)(?:\n|$)"

_CHASSIS = r"(?:Chassis|VIN)\s*(?:No|Number)?\s*[:\-_]?\s*([A-Z0-9\s]{5,25})"

_MODEL = r"(?:Model|Vehicle\s+Model)\s*[:\-]?\s*([A-Z0-9\s\-/\(\)]+?)(?:\n|Chassis|Engine|$)"

# Welcome / Loyalty bonus notes or table line items
_WELCOME_NOTE = r"((?:Welcome|Loyalty|Scrappage)\s+Bonus\s+Amount\s+is\s+Rs\.?\s*([\d,]+(?:\.\d+)?))"
_WELCOME_LINE = (
    r"(WELCOME\s+(?:BONUS|LOYALTY)|LOYALTY\s+BONUS|SCRAPPAGE\s+BONUS)"
    r"[^\d\n]*([\d,]+(?:\.\d+)?)"
)


def _extract_dealer(lines: list[str]) -> dict | None:
    # Scan up to the first 100 lines for dealer company suffixes
    for i, ln in enumerate(lines[:100], 1):
        ln = ln.strip()
        if len(ln) < 6:
            continue
        if re.search(r"(PVT\.?\s*LTD|MOTORS|AUTO|ENTERPRISES|AGENCY|LTD\.?)\b", ln, re.IGNORECASE):
            return {"text": ln, "line": i, "source": "python"}
    return None


def _extract_welcome_bonus(text: str, lines: list[str]) -> dict | None:
    norm_text = text.upper().replace("O", "0").replace("Q", "0").replace("I", "1").replace("S", "5").replace("Z", "7").replace("B", "8")
    m = re.search(_WELCOME_NOTE, norm_text, re.IGNORECASE)
    if m:
        return {
            "text": m.group(1).strip(),
            "amount": m.group(2).replace(",", ""),
            "line": line_of(_WELCOME_NOTE, lines),
            "source": "python",
        }
    m = re.search(_WELCOME_LINE, norm_text, re.IGNORECASE)
    if m:
        return {
            "text": m.group(1).strip(),
            "amount": m.group(2).replace(",", ""),
            "line": line_of(_WELCOME_LINE, lines),
            "source": "python",
        }
    return None


def extract_fields_from_text(text: str) -> dict:
    lines = text.splitlines()
    result = {}

    # dealership_name
    dealer = _extract_dealer(lines)
    if dealer:
        result["dealership_name"] = dealer

    # document_type
    val = first_match(_DOC_TYPE, text)
    if val:
        doc_type_text = val.strip().replace("  ", " ")
        # Map OCR typos back to normalized headers
        if any(k in doc_type_text.upper() for k in ("TAX", "INVAICO", "INVOLCE")):
            doc_type_text = "Tax Invoice"
        elif any(k in doc_type_text.upper() for k in ("GST", "GSL", "LVOICE")):
            doc_type_text = "GST Invoice"
        result["document_type"] = _field(doc_type_text, line_of(_DOC_TYPE, lines))

    # invoice_number
    val = first_match(_INV_NO, text)
    if val:
        result["invoice_number"] = _field(val.strip(), line_of(_INV_NO, lines))

    # invoice_date
    val = first_match(_INV_DATE, text)
    if val:
        result["invoice_date"] = _field(val.strip(), line_of(_INV_DATE, lines))

    # customer_name
    _CUST_NAME_PRIORITY = r"(?:Name|Customer\s+Name|Buyer(?:'s)?\s+Name)\s*[:\-]?\s*(?:\n)?\s*([A-Z][A-Z\s\.]+?)(?:\n|Bill|Ship|Invoice|Customer|$)"
    val = first_match(_CUST_NAME_PRIORITY, text)
    if not val:
        val = first_match(_CUST_NAME, text)
    if not val:
        val = first_match(_CUST_NAME_FALLBACK, text)
    if val:
        result["customer_name"] = _field(val.strip(), line_of(_CUST_NAME_PRIORITY, lines) or line_of(_CUST_NAME, lines) or line_of(_CUST_NAME_FALLBACK, lines))

    # chassis_number (strip spaces from extracted match)
    val = first_match(_CHASSIS, text)
    if val:
        clean_ch = re.sub(r"[^A-Z0-9]", "", val.upper())
        result["chassis_number"] = _field(clean_ch, line_of(_CHASSIS, lines))

    # new_vehicle_model
    val = first_match(_MODEL, text)
    if val and not any(k in val.upper() for k in ("PAN", "GST", "WEST BENGAL", "ROAD", "PHONE", "EMAIL", "BILL TO", "SHIP TO")):
        result["new_vehicle_model"] = _field(val.strip(), line_of(_MODEL, lines))
    else:
        models = ["THAR ROXX", "THAR", "BOLERO PIKUP", "BOLERO", "SUPRO", "JAYO", "XUV3XO", "XUV", "SCORPIO", "VEERO", "VIERO", "VLERO", "EERO"]
        for m in models:
            if m in text.upper():
                mapped = "VEERO" if m in ("VIERO", "VLERO", "EERO") else m
                result["new_vehicle_model"] = _field(mapped, 1)
                break
            elif m == "SUPRO" and "SUPRQ" in text.upper():
                result["new_vehicle_model"] = _field("SUPRO", 1)
                break

    # welcome_bonus_amount (text + amount)
    wb = _extract_welcome_bonus(text, lines)
    if wb:
        result["welcome_bonus_amount"] = wb

    return result


def try_extract_invoice_fields(pdf_path: str, claim_details: dict = None) -> dict | None:
    """
    Attempt to extract invoice fields using native PDF text or OCR if image-based.
    """
    from .reader_base import assist_extraction_with_portal
    text = extract_pdf_text(pdf_path)
    
    result = {}
    if len(text.strip()) >= 80:
        result = extract_fields_from_text(text)

    critical_fields = ["invoice_number", "customer_name", "chassis_number"]
    has_critical = all(k in result for k in critical_fields)

    parent = os.path.basename(os.path.dirname(pdf_path))
    fname = os.path.basename(pdf_path)
    cache_path = os.path.join("scratch", "ocr_txt", f"{parent}_{fname}.txt")

    if (len(result) < 4 or not has_critical) and not os.path.exists(cache_path):
        logging.info(f"[reader_invoice] Text extraction insufficient. Running EasyOCR fallback for {pdf_path}...")
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
            result = assist_extraction_with_portal(result, ocr_text, claim_details)
        except Exception as e:
            logging.error(f"[reader_invoice] OCR failed: {e}")

    result = assist_extraction_with_portal(result, text, claim_details)
    found = list(result.keys())
    logging.info(f"[welcome reader_invoice] Final extracted fields: {found}")
    return result
