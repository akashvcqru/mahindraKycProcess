"""
reader_invoice.py
=================
Python-native extractor for Tax Invoice / GST Invoice documents.

Fields extracted:
  dealership_name       — Company name from invoice header
  document_type         — "TAX INVOICE", "GST INVOICE", etc.
  invoice_no_date       — Invoice number + date
  customer_name         — Buyer / customer name
  oem_discount          — Scrappage / Loyalty bonus note + amount
  stamp_digitally_signed — "Yes" if "digitally signed" text found, "No" otherwise

Fields that CANNOT be extracted by Python (always AI):
  customer_signature    — visual, handwritten
  dealer_stamp          — visual stamp graphic
  stamp_signature       — visual signature on/near stamp

Returns None if image-based PDF.
"""

import re
import logging

from .reader_base import extract_pdf_text, is_text_based, _field, first_match, line_of


# ── Patterns ──────────────────────────────────────────────────────────────────

_DOC_TYPE = r"(TAX\s+INVOICE|GST\s+INVOICE|RETAIL\s+INVOICE|TAX\s+INVOLCE)"

# Invoice number — various formats
_INV_NO = r"(?:Invoice\s+No\.?|Bill\s+No\.?|Inv\.?\s*No\.?)\s*[:\-]?\s*([A-Z0-9]+)"
_INV_DATE = r"(?:Invoice\s+)?Date\s*[:\-]?\s*(\d{1,2}[\-\/\.]\d{1,2}[\-\/\.]\d{2,4}|\d{2}\-[A-Z]{3}\-\d{2,4})"

# Buyer / customer name (comes after "Name of Buyer", "Buyer", "Customer Name", "Bill To")
_CUST_NAME = (
    r"(?:Name\s+of\s+Buyer|Buyer(?:'s)?\s+Name|Customer\s+Name|Bill\s+To|Consignee)\s*[:\-]?\s*"
    r"([A-Z][A-Z\s\.]+?)(?:\n|GST|PAN|Addr|Mobile|Phone|$)"
)
_CUST_NAME_FALLBACK = r"(?:Buyer|Customer)\s*[:\-]\s*([A-Z][A-Z\s\.]+?)(?:\n|$)"

# OEM / Scrappage / Loyalty discount line
# Matches note-style: "Scrappage Bonus Amount is Rs.25000"
_OEM_NOTE = (
    r"((?:Scrappage|Loyalty)\s+Bonus\s+Amount\s+is\s+Rs\.?\s*([\d,]+(?:\.\d+)?))"
)
# Matches table line item style: "OEM LOYALTY DISCOUNT    25000"
_OEM_LINE = (
    r"(OEM\s+(?:LOYALTY\s+)?DISCOUNT|SCRAPPAGE\s+BONUS|LOYALTY\s+BONUS)"
    r"[^\d\n]*([\d,]+(?:\.\d+)?)"
)

# Digitally signed text
_DIGITAL_SIGN = r"(?:This\s+document\s+is\s+digitally\s+signed|Digitally\s+Signed|e-?Signed|Digital\s+Signature)"

# Dealership / company name — first substantial header line
_DEALER_TOP = r"^([A-Z][A-Za-z\s&\.\(\)\-]+(?:PVT\.?\s*LTD|MOTORS|AUTO|ENTERPRISES|AGENCY|LTD|CORP)[A-Za-z\s\.\-]*)$"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_dealer(lines: list[str]) -> dict | None:
    for i, ln in enumerate(lines[:20], 1):
        ln = ln.strip()
        if len(ln) < 6:
            continue
        if re.match(r"^[A-Z][A-Za-z\s&\.\(\)\-]+$", ln) and len(ln) >= 8:
            return {"text": ln, "line": i, "source": "python"}
    return None


def _extract_inv_no_date(text: str, lines: list[str]) -> dict | None:
    inv = first_match(_INV_NO, text)
    date = first_match(_INV_DATE, text)
    if inv:
        combined = inv
        if date:
            combined = f"{inv}, Date: {date}"
        return {"text": combined, "line": line_of(_INV_NO, lines), "source": "python"}
    return None


def _extract_oem(text: str, lines: list[str]) -> dict | None:
    # Try note-style first
    m = re.search(_OEM_NOTE, text, re.IGNORECASE)
    if m:
        return {
            "text":   m.group(1).strip(),
            "amount": m.group(2).replace(",", ""),
            "line":   line_of(_OEM_NOTE, lines),
            "source": "python",
        }
    # Try table line-item style
    m = re.search(_OEM_LINE, text, re.IGNORECASE)
    if m:
        return {
            "text":   m.group(1).strip(),
            "amount": m.group(2).replace(",", ""),
            "line":   line_of(_OEM_LINE, lines),
            "source": "python",
        }
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

def try_extract_invoice_fields(pdf_path: str) -> dict | None:
    """
    Attempt to extract invoice fields using native PDF text.

    Returns None if image-based.
    Returns dict of found fields (visual fields omitted — they need AI).
    """
    if not is_text_based(pdf_path):
        logging.info(f"[reader_invoice] {pdf_path} is image-based — skipping Python reader")
        return None

    text = extract_pdf_text(pdf_path)
    lines = text.splitlines()
    result = {}

    # dealership_name
    dealer = _extract_dealer(lines)
    if dealer:
        result["dealership_name"] = dealer

    # document_type
    val = first_match(_DOC_TYPE, text)
    if val:
        result["document_type"] = _field(val.strip().replace("  ", " "), line_of(_DOC_TYPE, lines))

    # invoice_no_date
    inv = _extract_inv_no_date(text, lines)
    if inv:
        result["invoice_no_date"] = inv

    # customer_name
    val = first_match(_CUST_NAME, text)
    if not val:
        val = first_match(_CUST_NAME_FALLBACK, text)
    if val:
        result["customer_name"] = _field(val.strip(), line_of(_CUST_NAME, lines))

    # oem_discount
    oem = _extract_oem(text, lines)
    if oem:
        result["oem_discount"] = oem

    # stamp_digitally_signed — purely text-based check
    if re.search(_DIGITAL_SIGN, text, re.IGNORECASE):
        result["stamp_digitally_signed"] = _field("Yes", line_of(_DIGITAL_SIGN, lines))
    else:
        result["stamp_digitally_signed"] = _field("No", 0)

    found = list(result.keys())
    logging.info(
        f"[reader_invoice] Extracted {len(found)}/6 text fields via Python: {found}"
    )
    return result
