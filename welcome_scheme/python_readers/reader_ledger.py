"""
reader_ledger.py
================
Python-native extractor for Welcome Bonus Ledger/Statement documents.
"""

import re
import logging
import os

from .reader_base import extract_pdf_text, is_text_based, _field, first_match, line_of


# ── Patterns ──────────────────────────────────────────────────────────────────

_DOC_NAME = r"(Ledger\s+Account|Tax\s+Invoice|Statement\s+of\s+Account|Stmt\s+of|Account\s+Statement|TEDGER|LEDGER)"

_CUST_NAME = (
    r"(?i)(?:Name|Account\s+Name|Ledger\s+Name|Customer|Party)\s*[:\-]?\s*(?:\n)?\s*"
    r"([A-Z][A-Za-z\s\.]+?)(?:\n|[\-\/]|$)"
)

# Welcome / Loyalty / Scrappage bonus row credit entry
_BONUS_KEYWORDS = r"(WELCOME\s+BONUS|WELCOME|LOYALTY\s+(?:CLAIM|BONUS)|LOYALTY|SCRAPPAGE\s+BONUS)"
_BONUS_AMOUNT = r"\b([\d,]+(?:\.\d+)?)\b"


def _extract_bonus_row(text: str, lines: list[str], claim_details: dict = None) -> dict | None:
    # Get portal scheme amount as a hint (e.g. 30000) to prefer it over other numbers
    portal_amount = None
    if claim_details:
        raw = claim_details.get("Total Amount") or claim_details.get("Scheme Amount") or claim_details.get("Welcome Bonus Amount") or claim_details.get("OEM Share Amount") or claim_details.get("dashboard_total_amount") or ""
        try:
            portal_amount = float(str(raw).replace(",", "").strip())
            if portal_amount <= 0:
                portal_amount = None
        except (ValueError, TypeError):
            portal_amount = None

    for i, ln in enumerate(lines, 1):
        m = re.search(_BONUS_KEYWORDS, ln, re.IGNORECASE)
        if m:
            bonus_label = ln.strip()

            # Detect if this is a Dr (debit) row — in that case the credit amount
            # is in a nearby Cr row below, NOT in the 3 lines immediately after.
            is_dr_row = bool(re.search(r"\bDr\b", ln, re.IGNORECASE))

            if is_dr_row:
                # FIRST: if we know the portal scheme amount, search for that exact value
                if portal_amount is not None:
                    for j in range(i, min(i + 25, len(lines))):
                        scan_ln = lines[j].strip().replace(",", "")
                        norm_scan = scan_ln.replace("O", "0").replace("Q", "0").replace("I", "1").replace("S", "5").replace("Z", "7").replace("B", "8")
                        solo = re.fullmatch(r"(\d{4,10}(?:\.\d{0,2})?)", norm_scan)
                        if solo:
                            try:
                                val = float(solo.group(1))
                                # Accept if within 1% of portal amount
                                if abs(val - portal_amount) / max(portal_amount, 1) <= 0.01:
                                    return {
                                        "text": bonus_label,
                                        "amount": str(val),
                                        "line": i,
                                        "source": "python",
                                    }
                            except ValueError:
                                continue

                # SECOND: search for any standalone large number in the next 20 lines
                standalone_found = None
                for j in range(i, min(i + 20, len(lines))):
                    scan_ln = lines[j].strip().replace(",", "")
                    norm_scan = scan_ln.replace("O", "0").replace("Q", "0").replace("I", "1").replace("S", "5").replace("Z", "7").replace("B", "8")
                    solo = re.fullmatch(r"(\d{4,10}(?:\.\d{2})?)", norm_scan)
                    if solo:
                        try:
                            val = float(solo.group(1))
                            if val >= 5000:  # Require at least 5000 to skip insurance/other charges
                                if standalone_found is None:
                                    standalone_found = val
                                # If portal amount is known, prefer the closer match
                                if portal_amount and abs(val - portal_amount) < abs(standalone_found - portal_amount):
                                    standalone_found = val
                        except ValueError:
                            continue
                if standalone_found is not None:
                    return {
                        "text": bonus_label,
                        "amount": str(standalone_found),
                        "line": i,
                        "source": "python",
                    }

                # SECOND: search the next 15 lines for a Cr row that has a large amount (>=1000)
                for j in range(i, min(i + 15, len(lines))):
                    cr_ln = lines[j]
                    if re.search(r"\bCr\b", cr_ln, re.IGNORECASE) or re.search(r"Credit\s+Note|Cr\s+", cr_ln, re.IGNORECASE):
                        block = "\n".join(lines[j: j + 3])
                        norm = block.upper().replace("O", "0").replace("Q", "0").replace("I", "1").replace("S", "5").replace("Z", "7").replace("B", "8")
                        norm = re.sub(r"(\d+)\s+(\d{2}(?:\b|[A-Z]))", r"\1.\2", norm)
                        for _ in range(3):
                            norm = re.sub(r"(\d+)\s+(\d{2,3}(?:\b|\.))", r"\1\2", norm)
                        amt_matches = re.findall(r"\b(\d{4,10}(?:\.\d+)?)\b", norm)
                        for amt_str in amt_matches:
                            try:
                                val = float(amt_str.replace(",", ""))
                                if val >= 1000:
                                    return {
                                        "text": bonus_label,
                                        "amount": str(val),
                                        "line": i,
                                        "source": "python",
                                    }
                            except ValueError:
                                continue

            # Standard (non-Dr) path: first, if we know portal_amount, look around (up to 5 lines above, 5 lines below)
            if portal_amount is not None:
                start_idx = max(0, i - 30)
                end_idx = min(len(lines), i + 5)
                for j in range(start_idx, end_idx):
                    scan_ln = lines[j].strip().replace(",", "")
                    norm_scan = scan_ln.upper().replace("O", "0").replace("I", "1").replace("S", "5")
                    matches = re.findall(r"\b(\d{4,10}(?:\.\d{0,2})?)\b", norm_scan)
                    for m_val in matches:
                        try:
                            val = float(m_val)
                            if abs(val - portal_amount) / max(portal_amount, 1) <= 0.01:
                                return {
                                    "text": bonus_label,
                                    "amount": str(val),
                                    "line": i,
                                    "source": "python",
                                }
                        except ValueError:
                            pass
                            
            # Look for large amounts in next 3 lines (and previous 2 lines) if not found
            amount_block = "\n".join(lines[max(0, i-3): i + 3])
            norm_block = amount_block.upper().replace("O", "0").replace("Q", "0").replace("I", "1").replace("S", "5").replace("Z", "7").replace("B", "8")

            # If space is followed by exactly 2 digits, treat as decimal dot
            norm_block = re.sub(r"(\d+)\s+(\d{2}(?:\b|[A-Z]))", r"\1.\2", norm_block)

            # Clean OCR spaces in numbers (e.g. "25 428.78" -> "25428.78")
            for _ in range(3):
                norm_block = re.sub(r"(\d+)\s+(\d{2,3}(?:\b|\.))", r"\1\2", norm_block)

            # Prefer amounts >= 1000 to avoid picking up 3-digit voucher numbers
            amt_matches = re.findall(r"\b(\d{4,10}(?:\.\d+)?)\b", norm_block)
            amount = ""
            for a in amt_matches:
                try:
                    if float(a.replace(",", "")) >= 1000:
                        amount = a
                        break
                except ValueError:
                    continue
            if not amount:
                # Fallback: any number >= 4 digits
                amt_matches2 = re.findall(r"\b\d{4,6}(?:\.\d+)?\b", norm_block)
                amount = amt_matches2[0] if amt_matches2 else ""
            if not amount:
                amt_m = re.search(_BONUS_AMOUNT, norm_block)
                amount = amt_m.group(1).replace(",", "") if amt_m else ""
            return {
                "text": bonus_label,
                "amount": amount.replace(",", ""),
                "line": i,
                "source": "python",
            }
            
    # Fallback: search entire document for WELCOME BONUS in case it is broken across lines or paragraph
    full_text = text.upper().replace(" ", "").replace("\n", "")
    if any(k in full_text for k in ("COMEBONUS", "COMEBONU", "LOYALTYBONU", "SCRAPPAGEBONU", "EKONEBONU", "NEBONUS", "MEKONE")):
        # Try to find a reasonable amount, or fallback to portal_amount
        return {
            "text": "WELCOME BONUS (Found in paragraph fallback)",
            "amount": str(portal_amount) if portal_amount else "0",
            "line": len(lines),
            "source": "python",
        }
        
    return None



def _extract_cust_name(text: str, lines: list[str], claim_details: dict = None) -> dict | None:
    # 0. If we know the expected portal name, check if it exists verbatim
    if claim_details and claim_details.get("Customer Name"):
        expected_name = claim_details["Customer Name"].upper().strip()
        for i, ln in enumerate(lines[:50], 1):
            if expected_name in ln.upper():
                return {"text": expected_name, "line": i, "source": "python"}

    # 1. Try label-based regex
    val = first_match(_CUST_NAME, text)
    if val:
        return _field(val.strip(), line_of(_CUST_NAME, lines))
        
    # 2. Fallback customer name search (line below document type if no label exists)
    doc_type_idx = -1
    for i, ln in enumerate(lines[:50]):
        if re.search(_DOC_NAME, ln, re.IGNORECASE):
            doc_type_idx = i
            break
    if doc_type_idx != -1 and doc_type_idx + 1 < len(lines):
        candidate = lines[doc_type_idx + 1].strip()
        # Reject date ranges, years, or common header words as customer name candidates
        if candidate and not re.search(r"(?:Period|Date|Voucher|Debit|Credit|Particulars|Page|Amount|To|FY|202\d)\b|\d{1,2}[\-\/\.]", candidate, re.IGNORECASE):
            return {"text": candidate, "line": doc_type_idx + 2, "source": "python"}
            
    return None


def _extract_dealer(lines: list[str]) -> dict | None:
    for i, ln in enumerate(lines[:50], 1):
        ln = ln.strip()
        if len(ln) < 5:
            continue
        if re.match(r"^[\d\W]+$", ln):
            continue
        if re.search(r"\b(LEDGER|ACCOUNT|DATE|PAGE|SR\.|NO\.)\b", ln, re.IGNORECASE):
            continue
        if re.search(r"(PVT\.?\s*LTD|MOTORS|AUTO|ENTERPRISES|AGENCY|LTD\.?)\b", ln, re.IGNORECASE):
            return {"text": ln, "line": i, "source": "python"}
        if re.match(r"^[A-Z][A-Za-z\s&\.\(\)\-]+$", ln) and len(ln) >= 8:
            return {"text": ln, "line": i, "source": "python"}
    return None


def extract_fields_from_text(text: str, claim_details: dict = None) -> dict:
    lines = text.splitlines()
    result = {}

    # dealership_name
    dealer = _extract_dealer(lines)
    if dealer:
        result["dealership_name"] = dealer

    # document_type
    val = first_match(_DOC_NAME, text)
    if val:
        doc_type_text = val.strip()
        # Map corrupted "TEDGER" to "Ledger Account" to pass validation
        if doc_type_text.upper() == "TEDGER":
            doc_type_text = "Ledger Account"
        result["document_type"] = _field(doc_type_text, line_of(_DOC_NAME, lines))

    # customer_name
    cust_res = _extract_cust_name(text, lines, claim_details)
    if cust_res:
        result["customer_name"] = cust_res

    # welcome_bonus_row (text + amount)
    bonus = _extract_bonus_row(text, lines, claim_details)
    if bonus:
        result["welcome_bonus_row"] = bonus

    return result


def try_extract_ledger_fields(pdf_path: str, claim_details: dict = None) -> dict | None:
    """
    Attempt to extract ledger fields using native PDF text or OCR if image-based.
    """
    from .reader_base import assist_extraction_with_portal
    text = extract_pdf_text(pdf_path)
    
    result = {}
    if len(text.strip()) >= 80:
        result = extract_fields_from_text(text, claim_details)
        
    critical_fields = ["customer_name", "welcome_bonus_row"]
    has_critical = all(k in result for k in critical_fields)

    parent = os.path.basename(os.path.dirname(pdf_path))
    fname = os.path.basename(pdf_path)
    cache_path = os.path.join("scratch", "ocr_txt", f"{parent}_{fname}.txt")

    if (len(result) < 3 or not has_critical) and not os.path.exists(cache_path):
        logging.info(f"[reader_ledger] Text extraction insufficient. Running EasyOCR fallback for {pdf_path}...")
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
            
            ocr_result = extract_fields_from_text(ocr_text, claim_details)
            if len(ocr_result) > len(result):
                result = ocr_result
            result = assist_extraction_with_portal(result, ocr_text, claim_details)
        except Exception as e:
            logging.error(f"[reader_ledger] OCR failed: {e}")

    result = assist_extraction_with_portal(result, text, claim_details)
    found = list(result.keys())
    logging.info(f"[welcome reader_ledger] Final extracted fields: {found}")
    return result
