"""
reader_ledger.py
================
Python-native extractor for Scrappage Scheme Ledger documents.

Fields extracted:
  dealership_name  — Company / dealer name from the document header
  customer_name    — Customer / account holder name
  document_name    — Document type (Ledger Account / Tax Invoice / etc.)
  scrappage_bonus  — Bonus line label + credit amount
  seal_stamp       — Cannot be detected by Python (always left to AI)

Returns None if the PDF is image-based.
"""

import re
import logging

from .reader_base import extract_pdf_text, is_text_based, _field, first_match, line_of


# ── Patterns ──────────────────────────────────────────────────────────────────

# Document type line
_DOC_NAME = r"(Ledger\s+Account|Tax\s+Invoice|Statement\s+of\s+Account|Stmt\s+of|Account\s+Statement)"

# Dealer / company name — usually the first long ALL-CAPS line
_DEALER_LINE = r"^([A-Z][A-Z\s&\.\(\)\-]+(?:PVT\.?\s*LTD|MOTORS|AUTO|ENTERPRISES|AGENCY|LTD|CORP)[A-Z\s\.\-]*)$"

# Customer name patterns
_CUST_NAME = (
    r"(?:Name|Account\s+Name|Ledger\s+Name|Customer|Party)\s*[:\-]\s*"
    r"([A-Z][A-Z\s\.]+?)(?:\n|$)"
)

# Scrappage / Welcome / Loyalty bonus line with amount
# Matches: "SCRAPPAGE BONUS   Cr   25000.00"  or "WELCOME BONUS  Cr  18000"
_BONUS_KEYWORDS = r"(SCRAPPAGE\s+BONUS|WELCOME\s+BONUS|LOYALTY\s+(?:CLAIM|BONUS)|EXCHANGE\s+BONUS|GREEN\s+BONUS|XMRT|LOYALTY\s+BONUS)"
_BONUS_AMOUNT   = r"(?:Cr\.?\s*)?([\d,]+(?:\.\d+)?)"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_bonus(text: str, lines: list[str]) -> dict | None:
    """
    Find the bonus line and extract label + credit amount.
    Returns a field dict or None.
    """
    for i, ln in enumerate(lines, 1):
        m = re.search(_BONUS_KEYWORDS, ln, re.IGNORECASE)
        if m:
            bonus_label = m.group(1).strip().upper()
            # Look for amount on same line or next 2 lines
            search_block = "\n".join(lines[i - 1 : i + 2])
            amt_m = re.search(_BONUS_AMOUNT, search_block)
            amount = amt_m.group(1).replace(",", "") if amt_m else ""
            return {
                "text":   bonus_label,
                "amount": amount,
                "line":   i,
                "source": "python",
            }
    return None


def _extract_dealer(lines: list[str]) -> dict | None:
    """Heuristic: first long non-empty ALL-CAPS or Title-Case header line."""
    for i, ln in enumerate(lines[:15], 1):  # Look in first 15 lines only
        ln = ln.strip()
        if len(ln) < 5:
            continue
        # Skip lines that are just numbers, dates, or generic labels
        if re.match(r"^[\d\W]+$", ln):
            continue
        if re.search(r"\b(LEDGER|ACCOUNT|DATE|PAGE|SR\.|NO\.)\b", ln, re.IGNORECASE):
            continue
        # Accept long title-ish lines
        if re.match(r"^[A-Z][A-Za-z\s&\.\(\)\-]+$", ln) and len(ln) >= 8:
            return {"text": ln, "line": i, "source": "python"}
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

def try_extract_ledger_fields(pdf_path: str) -> dict | None:
    """
    Attempt to extract ledger fields using native PDF text.

    Returns None if image-based.
    Returns dict of found fields (seal_stamp always omitted — needs AI).
    """
    if not is_text_based(pdf_path):
        logging.info(f"[reader_ledger] {pdf_path} is image-based — skipping Python reader")
        return None

    text = extract_pdf_text(pdf_path)
    lines = text.splitlines()
    result = {}

    # dealership_name
    dealer = _extract_dealer(lines)
    if dealer:
        result["dealership_name"] = dealer

    # document_name
    val = first_match(_DOC_NAME, text)
    if val:
        result["document_name"] = _field(val.strip(), line_of(_DOC_NAME, lines))

    # customer_name
    val = first_match(_CUST_NAME, text)
    if val:
        result["customer_name"] = _field(val.strip(), line_of(_CUST_NAME, lines))

    # scrappage_bonus (label + amount)
    bonus = _extract_bonus(text, lines)
    if bonus:
        result["scrappage_bonus"] = bonus

    found = list(result.keys())
    logging.info(f"[reader_ledger] Extracted {len(found)}/4 text fields via Python: {found}")
    return result
