"""
reader_oem.py
=============
Python-native extractor for Vahan OEM Scrapping Incentive documents.

NOTE: OEM documents are typically Vahan portal *screenshots* (image PDFs),
so text extraction usually returns very little.  This reader still tries,
and if it finds the table data it returns it instantly — otherwise returns
None so the caller falls back to Claude/OpenAI vision.

Fields extracted:
  certificate_deposit_no — Value from "Certificate Deposit" column (starts with COD)
  chassis_no             — New vehicle chassis number from the same table row
"""

import re
import logging

from .reader_base import extract_pdf_text, is_text_based, _field, first_match, line_of


# ── Patterns ──────────────────────────────────────────────────────────────────

# Matches a COD value like COD2026063AS01AD1927
_COD_VALUE = r"\b(COD\d{4,}[A-Z0-9]+)\b"

# Standard 17-char VIN / chassis (at least 12 alphanumeric)
_CHASSIS = r"\b([A-Z]{2,3}[A-Z0-9]{10,15})\b"

# Column header proximity: "Certificate Deposit" then value on next tokens
_CERT_DEPOSIT_COL = r"Certificate\s+Deposit\b[^\n]*\n([^\n]+)"


# ── Public API ─────────────────────────────────────────────────────────────────

def replace_common_confusions(s):
    return (
        s.upper()
        .replace("L", "1")
        .replace("I", "1")
        .replace("O", "0")
        .replace("Q", "0")
        .replace("U", "0")
        .replace("Z", "2")
        .replace("T", "7")
        .replace("S", "5")
        .replace("B", "8")
        .replace("G", "6")
    )


def try_extract_oem_fields(pdf_path: str, old_chassis: str = "", old_reg: str = "", new_chassis: str = "") -> dict | None:
    """
    Attempt to extract OEM Scrapping Incentive fields from native PDF text by locating
    the row that matches the new vehicle chassis or old vehicle details.
    """
    if not is_text_based(pdf_path):
        logging.info(f"[reader_oem] {pdf_path} is image-based — skipping Python reader")
        return None

    text = extract_pdf_text(pdf_path)
    lines = text.splitlines()
    result = {}

    clean_new_chassis = re.sub(r"[^A-Z0-9]", "", new_chassis.upper())
    clean_old_chassis = re.sub(r"[^A-Z0-9]", "", old_chassis.upper())
    clean_old_reg     = re.sub(r"[^A-Z0-9]", "", old_reg.upper())

    # We need to find the correct row. We'll scan each line.
    matched_line_idx = -1
    matched_cod = None
    matched_chassis = None

    # Step 1: Search by New Chassis suffix (usually last 8 digits, e.g. T2B34302)
    new_chassis_suffix = clean_new_chassis[-8:] if len(clean_new_chassis) >= 8 else clean_new_chassis
    adj_new_chassis_suffix = replace_common_confusions(new_chassis_suffix)

    for idx, line in enumerate(lines):
        line_clean = re.sub(r"[^A-Z0-9]", "", line.upper())
        adj_line_clean = replace_common_confusions(line_clean)
        
        if adj_new_chassis_suffix and adj_new_chassis_suffix in adj_line_clean:
            # Find the actual chassis token (starts or ends around where suffix was matched)
            words = re.findall(r"\b[A-Z0-9]{5,20}\b", line.upper())
            for w in words:
                if len(w) >= len(new_chassis_suffix):
                    w_suffix = w[-len(new_chassis_suffix):]
                    if replace_common_confusions(w_suffix) == adj_new_chassis_suffix:
                        matched_chassis = w
                        matched_line_idx = idx
                        logging.info(f"[reader_oem] Found matching row for new chassis suffix '{new_chassis_suffix}' at line {idx + 1}: '{line.strip()}'")
                        break
            if matched_line_idx != -1:
                break

    # Step 2: If new chassis not found, try to search by Old Chassis or Old Registration suffix
    if matched_line_idx == -1:
        adj_old_chassis_suffix = replace_common_confusions(clean_old_chassis[-6:] if len(clean_old_chassis) >= 6 else clean_old_chassis)
        adj_old_reg_suffix = replace_common_confusions(clean_old_reg[-5:] if len(clean_old_reg) >= 5 else clean_old_reg)
        
        for idx, line in enumerate(lines):
            line_clean = re.sub(r"[^A-Z0-9]", "", line.upper())
            adj_line_clean = replace_common_confusions(line_clean)
            
            # Check old chassis
            if adj_old_chassis_suffix and len(adj_old_chassis_suffix) >= 5 and adj_old_chassis_suffix in adj_line_clean:
                matched_line_idx = idx
                logging.info(f"[reader_oem] Found matching row for old chassis suffix at line {idx + 1}: '{line.strip()}'")
                break
            # Check old reg
            if adj_old_reg_suffix and len(adj_old_reg_suffix) >= 4 and adj_old_reg_suffix in adj_line_clean:
                matched_line_idx = idx
                logging.info(f"[reader_oem] Found matching row for old reg suffix at line {idx + 1}: '{line.strip()}'")
                break

    # Step 3: If we matched a row (line), extract the COD certificate and chassis from that line or adjacent lines
    if matched_line_idx != -1:
        # Search window: the matched line itself, plus 2 lines above and 2 lines below (to handle column splits)
        start_idx = max(0, matched_line_idx - 2)
        end_idx   = min(len(lines), matched_line_idx + 3)
        search_block = "\n".join(lines[start_idx:end_idx])

        # Find any COD value in this block (e.g. COD20260650DL3CV5516)
        cod_match = re.search(_COD_VALUE, search_block, re.IGNORECASE)
        if cod_match:
            matched_cod = cod_match.group(1).upper()

        # If we didn't find the chassis earlier, search for any 12+ alphanumeric chassis in this block that is not the COD
        if not matched_chassis:
            for m in re.finditer(_CHASSIS, search_block, re.IGNORECASE):
                candidate = m.group(1).upper()
                if not candidate.startswith("COD") and len(candidate) >= 12:
                    # Verify it matches our target new chassis suffix
                    candidate_clean = re.sub(r"[^A-Z0-9]", "", candidate)
                    if len(candidate_clean) >= len(new_chassis_suffix):
                        cand_suffix = candidate_clean[-len(new_chassis_suffix):]
                        if replace_common_confusions(cand_suffix) == adj_new_chassis_suffix:
                            matched_chassis = candidate
                            break

    # Step 4: Fallback to global search if line-by-line row matching found nothing
    if not matched_cod:
        matched_cod = first_match(_COD_VALUE, text)
    if not matched_chassis:
        for m in re.finditer(_CHASSIS, text):
            candidate = m.group(1)
            if not candidate.startswith("COD") and len(candidate) >= 12:
                matched_chassis = candidate
                break

    # Build the final output fields
    if matched_cod:
        result["certificate_deposit_no"] = _field(matched_cod, line_of(re.escape(matched_cod), lines))
    if matched_chassis:
        result["chassis_no"] = _field(matched_chassis, line_of(re.escape(matched_chassis), lines))

    found = list(result.keys())
    logging.info(f"[reader_oem] Extracted {len(found)}/2 fields via Python: {found}")
    return result

