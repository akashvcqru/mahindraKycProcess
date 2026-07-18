"""
reader_disclaimer.py
====================
Python-native extractor for Customer Disclaimer documents
(Loyalty / Scrappage Bonus through COD).

Fields extracted:
  dealership_name      — Company name from top-right header
  document_title       — Bold heading text
  customer_name        — Name from "I, <NAME>," declaration
  old_vehicle_details  — Registration No + Make + Model from section 1
  new_vehicle_details  — Chassis No + Engine No + Model from section 2
  benefit_amount       — INR amount from section 4

Fields that CANNOT be extracted by Python (always AI):
  customer_signature   — visual, handwritten
  dealer_stamp         — visual stamp graphic

Returns None if image-based PDF.
"""

import re
import logging

from .reader_base import extract_pdf_text, is_text_based, _field, first_match, line_of


# ── Patterns ──────────────────────────────────────────────────────────────────

_DOC_TITLE = (
    r"(Customer\s+Disclaimer[^\n]+(?:Loyalty|Scrappage)[^\n]+(?:COD|Bonus)[^\n]*)"
)

# Customer name from declaration paragraph: "I, Ankit Bhasin , residing..."
_CUST_DECL = r"(?:I|1|l|\|),\s*([^,]+?)\s*,\s*(?:residing|s/o|d/o|w/o|r/o|son|daughter|wife|do\s+hereby)"

# Old vehicle section
_OLD_REG   = r"Registration\s+Number\s*[:\-]\s*([A-Z0-9]{5,15})"
_OLD_MAKE  = r"Vehicle\s+Make\s*[:\-]\s*([A-Z][A-Z0-9\s]+?)(?:\n|Vehicle\s+Model|$)"
_OLD_MODEL = r"Vehicle\s+Model\s*[:\-]?\s*([A-Z][A-Z0-9\s\-]+?)(?:\n|New\s+Vehicle|$)"

# New vehicle section
_NEW_CHASSIS = r"Chassis\s+Number\s*[:\-]\s*([A-Z0-9]{5,20})"
_NEW_ENGINE  = r"Engine\s+Number\s*[:\-]\s*([A-Z0-9]{6,20})"
_NEW_MODEL   = r"New\s+Vehicle\s+Model\s*[:\-]\s*([A-Z][A-Z0-9\s\-]+?)(?:\n|Chassis|$)"

# Benefit amount: "INR 20000.0 from..."
_BENEFIT = r"INR\s*([\d,]+(?:\.\d+)?)"


# ── Public API ─────────────────────────────────────────────────────────────────

def try_extract_disclaimer_fields(pdf_path: str) -> dict | None:
    """
    Attempt to extract disclaimer fields using native PDF text or OCR if image-based.
    Returns dict of found fields (visual fields omitted — they need AI).
    """
    text = extract_pdf_text(pdf_path)
    
    if len(text.strip()) < 80:
        logging.info(f"[reader_disclaimer] {pdf_path} is image-based — running EasyOCR fallback...")
        try:
            import fitz
            import easyocr
            import numpy as np
            import io
            from PIL import Image
            doc = fitz.open(pdf_path)
            reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            ocr_text = []
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                res = reader.readtext(np.array(img), detail=0)
                ocr_text.extend(res)
            text = "\n".join(ocr_text)
        except Exception as e:
            logging.error(f"[reader_disclaimer] OCR failed: {e}")
            return None

    lines = text.splitlines()
    result = {}

    # document_title
    val = first_match(_DOC_TITLE, text)
    if val:
        result["document_title"] = _field(val.strip(), line_of(_DOC_TITLE, lines))

    # dealership_name — look for company-like name anywhere in the document (covers header and stamp at bottom)
    for i, ln in enumerate(lines, 1):
        ln = ln.strip()
        if len(ln) < 6:
            continue
        if re.search(r"(PVT\.?\s*LTD|MOTORS|AUTO|ENTERPRISES|AGENCY|LTD\.?)\b", ln, re.IGNORECASE):
            result["dealership_name"] = _field(ln, i)
            break

    # customer_name
    val = first_match(_CUST_DECL, text)
    if val:
        result["customer_name"] = _field(val.strip(), line_of(_CUST_DECL, lines))

    # old_vehicle_details
    old_reg   = first_match(_OLD_REG,   text)
    old_make  = first_match(_OLD_MAKE,  text)
    old_model = first_match(_OLD_MODEL, text)
    if old_reg or old_make or old_model:
        parts = []
        if old_reg:   parts.append(f"Reg: {old_reg.strip()}")
        if old_make:  parts.append(f"Make: {old_make.strip()}")
        if old_model: parts.append(f"Model: {old_model.strip()}")
        result["old_vehicle_details"] = _field(", ".join(parts), line_of(_OLD_REG, lines))

    # new_vehicle_details
    new_chassis = first_match(_NEW_CHASSIS, text)
    new_engine  = first_match(_NEW_ENGINE,  text)
    new_model   = first_match(_NEW_MODEL,   text)
    if new_chassis or new_engine or new_model:
        parts = []
        if new_model:   parts.append(f"Model: {new_model.strip()}")
        if new_chassis: parts.append(f"Chassis: {new_chassis.strip()}")
        if new_engine:  parts.append(f"Engine: {new_engine.strip()}")
        result["new_vehicle_details"] = _field(", ".join(parts), line_of(_NEW_CHASSIS, lines))

    # benefit_amount
    amounts = re.findall(_BENEFIT, text, re.IGNORECASE)
    if amounts:
        result["benefit_amount"] = _field(
            f"INR {amounts[0].replace(',', '')}", line_of(_BENEFIT, lines)
        )

    found = list(result.keys())
    logging.info(
        f"[reader_disclaimer] Extracted {len(found)}/6 text fields via Python: {found}"
    )
    return result
