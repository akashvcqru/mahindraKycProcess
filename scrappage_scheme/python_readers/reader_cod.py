"""
reader_cod.py
=============
Python-native extractor for Transfer Certificate of Deposit (COD) documents.

Fields extracted:
  certificate_no   — COD number at the top (e.g. COD20260470DL7CC4465)
  customer_name    — Owner / customer name
  registration_no  — Old vehicle registration number
  vehicle_make     — Vehicle manufacturer
  vehicle_model    — Vehicle model name

Returns None if the PDF is image-based (AI must be used instead).
Returns a dict with found fields otherwise; missing fields are omitted
(validator should call AI only for those).
"""

import re
import logging

from .reader_base import extract_pdf_text, is_text_based, _field, first_match, line_of


# ── Patterns ──────────────────────────────────────────────────────────────────

# Certificate No: COD20260470DL7CC4465
_CERT_NO = r"Certificate\s+(?:No|Number)\s*[:\-]?\s*(COD[A-Z0-9]+)"

# Customer / Owner name
# Matches: "Name : BHISMADEV DHRUA" or "Owner : RAKESH KUMAR"
_CUSTOMER_NAME = (
    r"(?:Customer\s+Name|Name\s+of\s+(?:Customer|Owner)|Owner(?:\s+Name)?)\s*[:\-]"
    r"\s*([A-Z][A-Z\s]+?)(?:\n|S/O|D/O|W/O|$)"
)
_CUSTOMER_NAME_FALLBACK = r"(?:^|\n)([A-Z]{2,}(?:\s+[A-Z]{2,})+)\s*\n"

# Vehicle Registration Number
_REG_NO = (
    r"(?:Vehicle\s+)?Registration\s+(?:No|Number)\s*[:\-]?\s*([A-Z0-9]{5,15})"
)

# Vehicle Make (in table)
_MAKE = r"Make\s*[:\-]\s*([A-Z][A-Z0-9\s\(\)\.]+?)(?:\n|Model|$)"

# Vehicle Model (in table)
_MODEL = r"Model\s*[:\-]\s*([A-Z][A-Z0-9\s\-]+?)(?:\n|Engine|CC|$)"


# ── Public API ─────────────────────────────────────────────────────────────────

def try_extract_cod_fields(pdf_path: str) -> dict | None:
    """
    Attempt to extract COD fields using native PDF text.

    Returns
    -------
    dict | None
        None  → PDF is image-based; caller must use AI.
        dict  → Fields found by Python (missing fields not in dict → use AI for those).
    """
    if not is_text_based(pdf_path):
        logging.info(f"[reader_cod] {pdf_path} is image-based — skipping Python reader")
        return None

    text = extract_pdf_text(pdf_path)
    lines = text.splitlines()
    result = {}

    # certificate_no
    val = first_match(_CERT_NO, text)
    if val:
        result["certificate_no"] = _field(val, line_of(_CERT_NO, lines))

    # customer_name
    val = first_match(_CUSTOMER_NAME, text)
    if not val:
        val = first_match(_CUSTOMER_NAME_FALLBACK, text, re.MULTILINE)
    if val:
        result["customer_name"] = _field(val.strip(), line_of(_CUSTOMER_NAME, lines))

    # registration_no
    val = first_match(_REG_NO, text)
    if val:
        result["registration_no"] = _field(val, line_of(_REG_NO, lines))

    # vehicle_make
    val = first_match(_MAKE, text)
    if val:
        result["vehicle_make"] = _field(val.strip(), line_of(_MAKE, lines))

    # vehicle_model
    val = first_match(_MODEL, text)
    if val:
        result["vehicle_model"] = _field(val.strip(), line_of(_MODEL, lines))

    found = list(result.keys())
    logging.info(f"[reader_cod] Extracted {len(found)}/5 fields via Python: {found}")
    return result
