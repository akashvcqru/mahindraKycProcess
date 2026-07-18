"""
reader_base.py
==============
Shared utilities used by welcome_scheme python readers.
"""

import logging
import os
import re

import fitz  # PyMuPDF


# Minimum characters of extracted text to consider a PDF "text-based"
_TEXT_MIN_CHARS = 80


def extract_pdf_text(pdf_path: str) -> str:
    """
    Return the full plain-text content of a PDF (all pages joined).
    Returns empty string if the file cannot be read or has no embedded text.
    """
    if not os.path.exists(pdf_path):
        return ""
        
    # Check if a cached OCR file exists in scratch/ocr_txt
    try:
        parent = os.path.basename(os.path.dirname(pdf_path))
        fname = os.path.basename(pdf_path)
        cache_path = os.path.join("scratch", "ocr_txt", f"{parent}_{fname}.txt")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_text = f.read()
            if len(cached_text.strip()) >= 50:
                logging.info(f"[reader_base] Loaded OCR text from cache: {cache_path}")
                return cached_text
    except Exception as cache_err:
        logging.warning(f"[reader_base] Cache lookup failed: {cache_err}")

    try:
        if pdf_path.lower().endswith(".pdf"):
            doc = fitz.open(pdf_path)
            pages_text = []
            for page in doc:
                pages_text.append(page.get_text("text"))
            return "\n".join(pages_text)
        else:
            return ""
    except Exception as exc:
        logging.warning(f"[reader_base] Could not extract text from {pdf_path}: {exc}")
        return ""


def is_text_based(pdf_path: str) -> bool:
    """
    Returns True if the PDF has enough embedded text to attempt Python extraction.
    """
    text = extract_pdf_text(pdf_path)
    return len(text.strip()) >= _TEXT_MIN_CHARS


def _field(text_value: str, line_no: int = 0) -> dict:
    """Build a standardised field dict returned by all readers."""
    return {
        "text": text_value.strip(),
        "line": line_no,
        "source": "python",
    }


def first_match(pattern: str, text: str, flags=re.IGNORECASE) -> str | None:
    """Return the first captured group of *pattern* in *text*, or None."""
    m = re.search(pattern, text, flags)
    if m:
        return m.group(1).strip()
    return None


def line_of(pattern: str, lines: list[str], flags=re.IGNORECASE) -> int:
    """Return the 1-based line number where *pattern* first matches, or 0."""
    for i, ln in enumerate(lines, 1):
        if re.search(pattern, ln, flags):
            return i
    return 0


def assist_extraction_with_portal(result: dict, text: str, claim_details: dict) -> dict:
    """
    Supplements regular expression extraction by searching the raw document text
    for values matching the portal claim details (handling common OCR substitutions).
    """
    if not claim_details:
        return result

    lines = text.splitlines()

    # 1. Customer Name assist
    portal_name = claim_details.get("Customer Name") or claim_details.get("Customer name", "")
    if portal_name:
        p_name_clean = re.sub(r"[^A-Z0-9\s]", "", portal_name.upper()).strip()
        p_words = p_name_clean.split()
        if len(p_words) >= 2:
            # Search for a line containing the portal name words (at least first name and last name)
            found_name = False
            for i, ln in enumerate(lines, 1):
                ln_up = ln.upper()
                if p_words[0] in ln_up and p_words[-1] in ln_up:
                    # Exclude bank names or company headers
                    if not any(k in ln_up for k in ("BANK", "LIMITED", "LTD", "SHREE", "AUTOMOTIVE", "MUTUAL", "INSURANCE")):
                        result["customer_name"] = _field(ln.strip(), i)
                        found_name = True
                        break
            if not found_name:
                # Fallback: check consecutive lines joined together (handles split name lines like Dev \n Nandi)
                for i in range(len(lines) - 1):
                    joined = (lines[i] + " " + lines[i+1]).upper()
                    if p_words[0] in joined and p_words[-1] in joined:
                        if not any(k in joined for k in ("BANK", "LIMITED", "LTD", "SHREE", "AUTOMOTIVE", "MUTUAL", "INSURANCE")):
                            result["customer_name"] = _field(lines[i].strip() + " " + lines[i+1].strip(), i + 2)
                            break

    # 2. Chassis Number assist
    portal_chassis = claim_details.get("Chassis No") or claim_details.get("Chassis Number", "")
    if portal_chassis:
        ch_norm = re.sub(r"[^A-Z0-9]", "", portal_chassis.upper())
        ch_norm = ch_norm.replace("O", "0").replace("I", "1").replace("Z", "7").replace("B", "8").replace("Q", "0").replace("G", "6").replace("S", "5").replace("C", "6").replace("L", "1").replace("T", "7")
        
        found_chassis = False
        for i, ln in enumerate(lines, 1):
            if found_chassis:
                break
            
            # Skip lines containing invoice, bill, GST, date, phone or mobile keywords
            if any(k in ln.upper() for k in ("INVOICE", "BILL", "GST", "DATE", "PHONE", "MOBILE")):
                continue
                
            # Clean the entire line of spaces and non-alphanumeric chars
            ln_clean = re.sub(r"[^A-Z0-9]", "", ln.upper())
            ln_norm_full = ln_clean.replace("O", "0").replace("I", "1").replace("Z", "7").replace("B", "8").replace("Q", "0").replace("G", "6").replace("S", "5").replace("C", "6").replace("L", "1").replace("T", "7")
            
            is_full_line_match = False
            if len(ch_norm) >= 6 and len(ln_norm_full) >= len(ch_norm):
                # 1. Substring check
                if ch_norm in ln_norm_full:
                    is_full_line_match = True
                # 2. Fuzzy suffix check
                else:
                    ln_suffix = ln_norm_full[-len(ch_norm):]
                    matches = sum(1 for x, y in zip(ln_suffix, ch_norm) if x == y)
                    if matches / len(ch_norm) >= 0.60:
                        is_full_line_match = True
                # 3. Fuzzy numeric suffix check
                if not is_full_line_match:
                    num_full = re.sub(r"[^0-9]", "", ln_norm_full)
                    num_portal = re.sub(r"[^0-9]", "", ch_norm)
                    if len(num_full) >= 4 and len(num_portal) >= 4:
                        n1 = num_full[-5:]
                        n2 = num_portal[-5:]
                        overlap = sum(1 for x, y in zip(n1, n2) if x == y)
                        if overlap / max(len(n1), len(n2)) >= 0.60:
                            is_full_line_match = True
            
            if is_full_line_match:
                # Find the best matching word inside the line
                words = [w for w in re.split(r"[^A-Z0-9]", ln.upper()) if w]
                best_word = ln.strip()
                for word in words:
                    w_nums = re.sub(r"[^0-9]", "", word)
                    ch_nums = re.sub(r"[^0-9]", "", portal_chassis)
                    if len(w_nums) >= 3 and w_nums in ch_nums:
                        # Reconstruct the chassis word around it or use the line
                        best_word = word
                        break
                result["chassis_number"] = _field(best_word, i)
                found_chassis = True
                break
                
            # Word-by-word fallback
            words = [w for w in re.split(r"[^A-Z0-9]", ln.upper()) if w]
            for word in words:
                w_norm = word.replace("O", "0").replace("I", "1").replace("Z", "7").replace("B", "8").replace("Q", "0").replace("G", "6").replace("S", "5").replace("C", "6").replace("L", "1").replace("T", "7")
                
                if len(ch_norm) >= 6 and len(w_norm) >= 6 and (ch_norm in w_norm or w_norm in ch_norm):
                    result["chassis_number"] = _field(word.strip(), i)
                    found_chassis = True
                    break
                nums_w = re.sub(r"[^0-9]", "", w_norm)
                nums_c = re.sub(r"[^0-9]", "", ch_norm)
                if len(nums_w) >= 4 and len(nums_c) >= 4 and nums_w[-4:] == nums_c[-4:]:
                    if abs(len(w_norm) - len(ch_norm)) <= 10:
                        result["chassis_number"] = _field(word.strip(), i)
                        found_chassis = True
                        break
                if len(ch_norm) >= 6 and len(w_norm) >= 6:
                    w_suffix = w_norm[-len(ch_norm):]
                    matches = sum(1 for x, y in zip(w_suffix, ch_norm) if x == y)
                    if matches / len(ch_norm) >= 0.60:
                        result["chassis_number"] = _field(word.strip(), i)
                        found_chassis = True
                        break

    # 3. Invoice Number assist
    portal_inv = claim_details.get("Invoice No") or claim_details.get("Invoice Number", "")
    if portal_inv:
        inv_norm = re.sub(r"[^A-Z0-9]", "", portal_inv.upper())
        inv_norm = inv_norm.replace("O", "0").replace("I", "1").replace("Z", "7").replace("B", "8").replace("Q", "0").replace("G", "6").replace("S", "5")
        
        found_inv = False
        for i, ln in enumerate(lines, 1):
            if found_inv:
                break
            for word in ln.split():
                w_clean = re.sub(r"[^A-Z0-9]", "", word.upper())
                w_norm = w_clean.replace("O", "0").replace("I", "1").replace("Z", "7").replace("B", "8").replace("Q", "0").replace("G", "6").replace("S", "5")
                
                is_match = False
                if len(inv_norm) >= 6 and len(w_norm) >= 6:
                    if inv_norm in w_norm or w_norm in inv_norm:
                        is_match = True
                    else:
                        matches = sum(1 for x, y in zip(w_norm, inv_norm) if x == y)
                        if matches / max(len(w_norm), len(inv_norm)) >= 0.70:
                            is_match = True
                            
                if is_match:
                    # Filter out matches like "DATE" or "ORDER"
                    if not any(k in word.upper() for k in ("DATE", "ORDER", "PHONE", "MOBILE", "GST")):
                        result["invoice_number"] = _field(word.strip(), i)
                        found_inv = True
                        break

    # 4. Invoice Date assist
    portal_date = claim_details.get("Invoice Date") or claim_details.get("Invoice date", "")
    if portal_date:
        # Parse portal date robustly (handles Month Name and compact formats)
        from datetime import datetime
        def parse_portal_d(s):
            s_clean = s.strip()
            months_map = {"january":"01","jan":"01","february":"02","feb":"02","march":"03","mar":"03","april":"04","apr":"04","may":"05","june":"06","jun":"06","july":"07","jul":"07","august":"08","aug":"08","september":"09","sep":"09","oct":"10","november":"11","nov":"11","december":"12","dec":"12"}
            for name, num in months_map.items():
                p = re.compile(rf"\b{name}\b", re.IGNORECASE)
                s_clean, count = p.subn(num, s_clean)
                if count > 0:
                    break
            s_clean = re.sub(r"[^0-9]", "-", s_clean)
            s_clean = re.sub(r"-+", "-", s_clean).strip("-")
            digits = re.sub(r"[^0-9]", "", s_clean)
            if len(digits) == 8:
                s_clean = f"{digits[:2]}-{digits[2:4]}-{digits[4:]}"
            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y", "%y-%m-%d", "%d-%b-%y", "%d.%m.%y"):
                try:
                    return datetime.strptime(s_clean, fmt).date()
                except ValueError:
                    pass
            return None

        p_dt = parse_portal_d(portal_date)
        if p_dt:
            day_str = str(p_dt.day)
            day_padded = f"{p_dt.day:02d}"
            month_str = f"{p_dt.month:02d}"
            year_str = str(p_dt.year)
            year_short = year_str[-2:]
            
            months_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
            month_name = months_names[p_dt.month - 1]
            
            for i, ln in enumerate(lines, 1):
                ln_up = ln.upper()
                # Check if line contains day and year, and either month number or month name
                if (day_str in ln_up or day_padded in ln_up) and (year_str in ln_up or year_short in ln_up):
                    if month_str in ln_up or month_name in ln_up:
                        date_match = re.search(r"(\d{1,2}[\-\/\.]?(?:[A-Z]{3,9}|\d{1,2})[\-\/\.]?\d{2,4})", ln_up)
                        if date_match:
                            result["invoice_date"] = _field(date_match.group(1), i)
                            break
                        
    return result

