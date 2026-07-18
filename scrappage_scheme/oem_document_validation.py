import base64
import io
import json
import logging
import os
import re
import time
import sys

import fitz
import requests
from PIL import Image

# Appending root workspace path for automate_login functions
sys.path.append(os.path.abspath("."))
try:
    from automate_login import find_chassis_in_text, compare_values_robust
except ImportError:
    def compare_values_robust(v1, v2, fuzzy_threshold=80):
        c1 = re.sub(r"[^A-Z0-9]", "", str(v1).upper())
        c2 = re.sub(r"[^A-Z0-9]", "", str(v2).upper())
        if c1 == c2:
            return "MATCH", 100
        return "MISMATCH", 0

    def find_chassis_in_text(text, target_chassis, match_last_8=False):
        if not target_chassis:
            return None
        target_clean = re.sub(r"[^A-Z0-9]", "", target_chassis.upper())
        if match_last_8:
            target_clean = target_clean[-8:]
        text_clean = re.sub(r"[^A-Z0-9]", "", text.upper())
        if target_clean in text_clean:
            return target_clean
        return None


def replace_common_confusions(s):
    """Normalize common OCR confusions so mismatch doesn't occur due to a single digit."""
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


def ocr_adjusted_suffix_match(val1, val2, suffix_len=8):
    """Robust suffix comparison of length suffix_len with OCR confusion tolerance."""
    if not val1 or not val2:
        return False
    c1 = re.sub(r"[^A-Z0-9]", "", str(val1).upper())
    c2 = re.sub(r"[^A-Z0-9]", "", str(val2).upper())
    
    if len(c1) < suffix_len or len(c2) < suffix_len:
        min_len = min(len(c1), len(c2))
        if min_len == 0:
            return False
        s1 = c1[-min_len:]
        s2 = c2[-min_len:]
    else:
        s1 = c1[-suffix_len:]
        s2 = c2[-suffix_len:]
        
    return replace_common_confusions(s1) == replace_common_confusions(s2)


def compare_certificate_to_reg(cert_no, reg_no):
    if not cert_no or not reg_no:
        return False
    c1 = re.sub(r"[^A-Z0-9]", "", reg_no.upper())
    c2 = re.sub(r"[^A-Z0-9]", "", cert_no.upper())
    
    # Replace common OCR confusions
    c1_norm = replace_common_confusions(c1)
    c2_norm = replace_common_confusions(c2)
    
    # Match from the back (suffix match)
    if c2_norm.endswith(c1_norm) or c1_norm.endswith(c2_norm):
        return True
        
    # Suffix match for at least 6 characters
    min_suffix = min(6, len(c1_norm))
    if len(c1_norm) >= min_suffix and len(c2_norm) >= min_suffix:
        if c2_norm[-min_suffix:] == c1_norm[-min_suffix:]:
            return True
            
    return False


def compare_chassis_robust(doc_chassis, portal_chassis):
    if not doc_chassis or not portal_chassis:
        return False
    c1 = re.sub(r"[^A-Z0-9]", "", portal_chassis.upper())
    c2 = re.sub(r"[^A-Z0-9]", "", doc_chassis.upper())
    
    # 1. Direct match with OCR normalization
    if replace_common_confusions(c1) == replace_common_confusions(c2):
        return True
        
    # 2. Suffix match (last 8 characters)
    if len(c1) >= 8 and len(c2) >= 8:
        if replace_common_confusions(c1[-8:]) == replace_common_confusions(c2[-8:]):
            return True
            
    # 3. Suffix match (last 6 characters) as fallback
    if len(c1) >= 6 and len(c2) >= 6:
        if replace_common_confusions(c1[-6:]) == replace_common_confusions(c2[-6:]):
            return True
            
    return False



def find_chassis_in_text_ocr(text, target_chassis, suffix_len=8):
    """Scan text for any token whose suffix matches target_chassis suffix under OCR normalization."""
    if not target_chassis:
        return None
    target_clean = re.sub(r"[^A-Z0-9]", "", target_chassis.upper())
    if len(target_clean) >= suffix_len:
        target_suffix = target_clean[-suffix_len:]
    else:
        target_suffix = target_clean
        
    target_adj = replace_common_confusions(target_suffix)
    
    # Split text into uppercase words
    words = re.findall(r"\b[A-Z0-9]{4,25}\b", text.upper())
    for w in words:
        if len(w) >= len(target_suffix):
            w_suffix = w[-len(target_suffix):]
            if replace_common_confusions(w_suffix) == target_adj:
                return w
                
    return None



# ── System Prompt for Vahan OEM Scrapping Incentive Document ─────────────────
OEM_PROMPT = """You are an expert document analysis AI analyzing a multi-page Vahan portal screenshot (OEM Scrapping Incentive document).

This document contains MULTIPLE pages stitched vertically. These pages show:
- Page with new vehicle registration details at the top (header shows "Registration No: XXXXXX" — IGNORE this registration number, it belongs to the NEW vehicle, NOT what we need)
- A page showing "Certificate of Deposit(COD) Details" (or "Certificate Deposit(COD) Details") with fields like "Certificate of Deposit(COD) Number" (or "Certificate Deposit(COD) Number" / "Certificate Deposit Number") and "Old Registration Number"
- A page titled "OEM SCRAPPING INCENTIVE" with a table titled "Details of CDs Applied for OEM Scrapping Incentive" containing THREE columns:
  - Column 1: "Chassis Number" (new vehicle chassis numbers)
  - Column 2: "Engine Number"
  - Column 3: "Certificate Deposit" (this contains values like COD2026063AS01AD1927 — this is what we need)

YOUR TASK:
Extract ONLY these 2 fields:

1. certificate_deposit_no
   - CRITICAL: You must locate the table titled "Details of CDs Applied for OEM Scrapping Incentive"
   - In that table, find the SPECIFIC ROW whose "Chassis Number" column matches the target chassis number (will be provided in context)
   - Extract the "Certificate Deposit" column value from THAT MATCHING ROW (it always starts with "COD..." followed by digits and letters)
   - DO NOT extract the registration number shown in the page header (e.g. "AS01GU7475" — this is the new vehicle's Vahan registration, NOT the certificate deposit)
   - The correct value MUST start with "COD" and look like: COD2026063AS01AD1927

2. chassis_no
   - The new vehicle chassis number from the same matching row in the "Chassis Number" column of the OEM Scrapping Incentive table
   - It looks like: MA1TA2YS2T2E91998

For each field return:
- The exact text found
- Which line number (approx) it appears on
- A crop bounding box as percentage of TOTAL stitched image height/width: {top%, left%, bottom%, right%}
  (IMPORTANT: Coordinates must reflect the actual position in the full stitched image. The OEM table is usually in the bottom portion. Do NOT hallucinate.)

Respond ONLY in this JSON format (no markdown, no extra text):
{
  "certificate_deposit_no": {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "chassis_no":             {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}}
}"""


def _render_pdf_to_pil(pdf_path):
    if pdf_path.lower().endswith(".pdf"):
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200)
        png_bytes = pix.tobytes("png")
        return Image.open(io.BytesIO(png_bytes)).convert("RGB")
    else:
        return Image.open(pdf_path).convert("RGB")


def _pil_to_b64(pil_img):
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _call_openai(full_b64, old_chassis=None, old_reg=None, new_chassis=None, max_retries=3):
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logging.error("OPENAI_API_KEY not found in environment.")
        return None, "OPENAI_API_KEY not found in environment."

    prompt = OEM_PROMPT
    if old_chassis or old_reg or new_chassis:
        prompt += "\n\nCRITICAL CONTEXT / TARGET VALUES TO SEARCH FOR IN THE TABLE:\n"
        if old_chassis:
            prompt += f"- Target Old Chassis No (Certificate Deposit Number): Search for a value matching or containing \"{old_chassis}\" (e.g. \"{old_chassis}\").\n"
        if old_reg:
            prompt += f"- Target Old Registration No: Search for a value containing \"{old_reg}\" (e.g. \"{old_reg}\").\n"
        if new_chassis:
            prompt += f"- Target New Chassis No: Search for a value whose last 8 characters match \"{new_chassis[-8:] if len(new_chassis) >= 8 else new_chassis}\" (or matches full chassis \"{new_chassis}\").\n"
        prompt += "\nIf there is a table or list containing multiple rows, please locate the specific row that matches either the Target Old Chassis/Reg No, or the Target New Chassis No, and extract the fields 'certificate_deposit_no' and 'chassis_no' ONLY from that matching row."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{full_b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 1000,
        "temperature": 0.0,
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            try:
                content = content.replace("```json", "").replace("```", "").strip()
                return json.loads(content), None
            except json.JSONDecodeError:
                logging.error(f"Failed to parse JSON. Raw content: {content}")
                return None, f"JSONDecodeError: OpenAI returned non-JSON text: {content[:100]}..."
        except Exception as exc:
            if attempt == max_retries - 1:
                logging.error(f"OpenAI OEM call failed: {exc}")
                return None, f"OpenAI Error: {exc}"
            time.sleep(2)
    return None, "Max retries exceeded."


FIELD_MAPPING = {
    "certificate_deposit_no": "Certificate of Deposit No (Old Chassis)",
    "chassis_no":             "New Vehicle Chassis Number"
}

FIELD_ORDER = ["certificate_deposit_no", "chassis_no"]


def _pair_crops(pil_img, extracted):
    width, height = pil_img.size
    results = []

    for key in FIELD_ORDER:
        if key not in extracted:
            continue
        data = extracted[key]
        label = FIELD_MAPPING.get(key, key)
        val = data.get("text", "")

        crop_info = data.get("crop", {})
        top_pct    = crop_info.get("top",    0)   / 100.0
        left_pct   = crop_info.get("left",   0)   / 100.0
        bottom_pct = crop_info.get("bottom", 100) / 100.0
        right_pct  = crop_info.get("right",  100) / 100.0

        PAD_X, PAD_Y = 50, 50
        x1 = max(0, int(left_pct   * width)  - PAD_X)
        y1 = max(0, int(top_pct    * height) - PAD_Y)
        x2 = min(width,  int(right_pct  * width)  + PAD_X)
        y2 = min(height, int(bottom_pct * height) + PAD_Y)

        if x2 <= x1: x2 = min(width,  x1 + 10)
        if y2 <= y1: y2 = min(height, y1 + 10)

        crop_b64 = ""
        try:
            crop_img = pil_img.crop((x1, y1, x2, y2))
            buf = io.BytesIO()
            crop_img.save(buf, format="PNG")
            crop_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as crop_err:
            logging.error(f"Crop error for OEM field '{key}': {crop_err}")

        results.append({"field": label, "value": val, "crop_b64": crop_b64})

    return results


def _generate_mock_response(pil_img):
    mock = {
        "certificate_deposit_no": {"text": "API Error", "line": 10, "crop": {"top": 10, "left": 0, "bottom": 30, "right": 100}},
        "chassis_no":             {"text": "API Error", "line": 20, "crop": {"top": 40, "left": 0, "bottom": 60, "right": 100}}
    }
    return _pair_crops(pil_img, mock)


# ── PUBLIC: validate_oem (called by processor.py) ─────────────────────────
def validate_oem(pdf_path, claim_details, old_vehicle_details, data_store):
    """
    Validates a Scrappage OEM Certificate of Deposit document.
    Returns (success: bool, message: str).
    """
    logging.info(f"Validating Scrappage OEM Document: {pdf_path}")

    if not os.path.exists(pdf_path):
        logging.error("OEM PDF not found.")
        return False, "OEM PDF not found"

    try:
        pil_img = _render_pdf_to_pil(pdf_path)
    except Exception as exc:
        logging.error(f"Failed to render OEM PDF {pdf_path}: {exc}")
        return False, f"Failed to load image: {exc}"

    old_chassis_web = old_vehicle_details.get("Chassis No", "").strip()
    old_reg_web = old_vehicle_details.get("Reg. No", old_vehicle_details.get("Reg No", old_vehicle_details.get("Registration No", ""))).strip()
    if not old_reg_web and claim_details:
        old_reg_web = claim_details.get("Reg. No", claim_details.get("Reg No", claim_details.get("Registration No", ""))).strip()
    new_chassis_web = claim_details.get("Chassis No", "").strip()

    # ── Fast path: Python reader (text-based OEM PDFs only) ───────────────────
    from .python_readers.reader_oem import try_extract_oem_fields
    python_data = try_extract_oem_fields(
        pdf_path,
        old_chassis=old_chassis_web,
        old_reg=old_reg_web,
        new_chassis=new_chassis_web
    )
    extracted = None

    is_python_provider = (os.getenv("AI_PROVIDER", "").strip().upper() == "PYTHON")

    if is_python_provider:
        # Build extracted from python_data (or empty if none found, to let checks fail normally or pass)
        extracted = {}
        if python_data:
            for k, v in python_data.items():
                line_no = v.get("line", 0)
                if line_no > 0:
                    pct = (line_no / 45.0) * 100
                    crop = {
                        "top": max(0, int(pct - 10)),
                        "left": 0,
                        "bottom": min(100, int(pct + 10)),
                        "right": 100
                    }
                else:
                    crop = {"top": 0, "left": 0, "bottom": 100, "right": 100}
                extracted[k] = {"text": v.get("text", ""), "line": line_no, "crop": crop}
        
        logging.info("[validate_oem] Running in Python-only mode — skipped AI")

    if not extracted and not is_python_provider:
        try:
            pil_img = _render_pdf_to_pil(pdf_path)
        except Exception as exc:
            logging.error(f"Failed to render OEM PDF {pdf_path}: {exc}")
            return False, f"Failed to load image: {exc}"
        full_b64 = _pil_to_b64(pil_img)
        extracted, err_msg = _call_openai(
            full_b64,
            old_chassis=old_chassis_web,
            old_reg=old_reg_web,
            new_chassis=new_chassis_web
        )

    if not extracted:
        # Instead of failing immediately, allow the text/OCR fallbacks below to attempt extraction.
        # Initialize empty dict so .get() calls below don't throw errors.
        extracted = {}
    # Merge Python-extracted text fields into AI result
    if python_data and not is_python_provider:
        for k, v in python_data.items():
            if not extracted.get(k, {}).get("text"):
                extracted[k] = {"text": v.get("text", ""), "line": v.get("line", 0), "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}

    if data_store:
        data_store.update_doc_data("oem_document", extracted)

    issues = []
    text_str = None

    # 1. Certificate of Deposit number must match old vehicle Chassis No or Reg No if COD prefix is missing
    cert_no = extracted.get("certificate_deposit_no", {}).get("text", "").strip()

    if not cert_no:
        # Fallback: Try to extract text/OCR to find any COD number in the document
        try:
            doc = fitz.open(pdf_path)
            text_str = "\n".join(page.get_text() for page in doc)
            if len(text_str.strip()) < 10:
                import easyocr
                import numpy as np
                import io
                from PIL import Image
                reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                ocr_text = []
                for page in doc:
                    pix = page.get_pixmap(dpi=150)
                    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                    res = reader.readtext(np.array(img), detail=0)
                    ocr_text.extend(res)
                text_str = " ".join(ocr_text)
        except Exception as exc:
            logging.error(f"Fallback text extraction failed for Certificate of Deposit No: {exc}")
            text_str = ""

        # Search for COD value in the extracted text
        # Find all words that look like a COD number
        words = re.findall(r"\b(?:COD|CO0|C0D|C00)?[A-Z0-9]{8,25}\b", text_str, re.IGNORECASE)
        best_candidate = None
        best_score = 0
        
        for w in words:
            w_upper = w.upper()
            if not w_upper.startswith(("COD", "CO0", "C0D", "C00")) and "COD" not in w_upper:
                continue
            
            # Clean and normalize candidate
            w_clean = re.sub(r"[^A-Z0-9]", "", w_upper)
            
            # Check direct match with old chassis
            if old_chassis_web:
                status, score = compare_values_robust(w_clean, old_chassis_web)
                if status.startswith("MATCH") and score > best_score:
                    best_candidate = w_clean
                    best_score = score
                    
            # Check direct match with old reg
            if old_reg_web:
                status, score = compare_values_robust(w_clean, old_reg_web)
                if status.startswith("MATCH") and score > best_score:
                    best_candidate = w_clean
                    best_score = score
                    
        if best_candidate:
            cert_no = best_candidate
            logging.info(f"Fallback: Found best matching certificate_deposit_no '{cert_no}' in raw text / OCR (score={best_score})")
        else:
            # If no good fuzzy match found, fallback to the first word that starts with COD (or similar)
            cod_match = re.search(r"\b(COD\d{4,}[A-Z0-9]+)\b", text_str, re.IGNORECASE)
            if not cod_match:
                cod_match = re.search(r"\b(COD[A-Z0-9]+)\b", text_str, re.IGNORECASE)
            if cod_match:
                cert_no = cod_match.group(1).upper()
                logging.info(f"Fallback: Found first certificate_deposit_no '{cert_no}' in raw text / OCR")
                
        if cert_no:
            extracted["certificate_deposit_no"] = {
                "text": cert_no,
                "line": 0,
                "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}
            }

    if not cert_no:
        issues.append("Certificate of Deposit No not found in document")
    else:
        # Check if the portal chassis number has the 'COD' prefix
        is_cod_chassis = False
        if old_chassis_web:
            old_chassis_clean = re.sub(r"[^A-Z0-9]", "", old_chassis_web.upper())
            if old_chassis_clean.startswith(("COD", "CO0", "C0D", "C00")):
                is_cod_chassis = True
                
        if is_cod_chassis:
            if not compare_certificate_to_reg(cert_no, old_chassis_web):
                issues.append(
                    f"Certificate No mismatch (Document Certificate No: '{cert_no}' does not match old vehicle chassis: '{old_chassis_web}')"
                )
        else:
            # Fallback: check Reg. No from old vehicle details against the certificate number in the document
            old_reg_web = old_vehicle_details.get("Reg. No", old_vehicle_details.get("Reg No", old_vehicle_details.get("Registration No", ""))).strip()
            if not old_reg_web and claim_details:
                old_reg_web = claim_details.get("Reg. No", claim_details.get("Reg No", claim_details.get("Registration No", ""))).strip()
                
            if old_reg_web:
                if not compare_certificate_to_reg(cert_no, old_reg_web):
                    issues.append(
                        f"Certificate No mismatch (Document Certificate No: '{cert_no}' does not match old vehicle registration: '{old_reg_web}')"
                    )
            else:
                # If neither chassis with COD nor Reg No is found, fallback to check chassis if available
                if old_chassis_web:
                    if not compare_certificate_to_reg(cert_no, old_chassis_web):
                        issues.append(
                            f"Certificate No mismatch (Document Certificate No: '{cert_no}' does not match old vehicle chassis: '{old_chassis_web}')"
                        )

    # 2. Chassis Number in the document (new vehicle chassis) last 8 characters must match dashboard claim details
    doc_chassis = extracted.get("chassis_no", {}).get("text", "").strip()
    new_chassis_web = claim_details.get("Chassis No", "").strip()

    if not doc_chassis:
        # Check raw text backup just in case LLM missed the structured new chassis key but it exists in the document
        if text_str is None:
            try:
                # Join text of ALL pages since the table might be on the last page (e.g. page 4)
                doc = fitz.open(pdf_path)
                text_str = "\n".join(page.get_text() for page in doc)
                if len(text_str.strip()) < 10:
                    # It's an image-based PDF, use EasyOCR
                    import easyocr
                    import numpy as np
                    import io
                    from PIL import Image
                    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                    ocr_text = []
                    for page in doc:
                        pix = page.get_pixmap(dpi=150)
                        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                        res = reader.readtext(np.array(img), detail=0)
                        ocr_text.extend(res)
                    text_str = " ".join(ocr_text)
            except Exception:
                text_str = ""
        
        matched_new = find_chassis_in_text_ocr(text_str, new_chassis_web, suffix_len=8)
        if not matched_new:
            matched_new = find_chassis_in_text_ocr(text_str, new_chassis_web, suffix_len=5)
            if matched_new:
                logging.info(f"Fallback matched new chassis in text_str using shorter suffix_len=5")
        if not matched_new:
            issues.append("New Chassis number not found in OEM Document")
    elif new_chassis_web:
        matched_new = compare_chassis_robust(doc_chassis, new_chassis_web)
        if not matched_new:
            issues.append(
                f"New Chassis mismatch (Document Chassis: '{doc_chassis}' does not match last 8 digits of dashboard: '{new_chassis_web}')"
            )

    if issues:
        return False, "; ".join(issues)
    return True, "OEM Document Validated"


# ── PUBLIC: process_oem_visual (called by app_ui.py) ───────────────────────
def process_oem_visual(pdf_path, old_chassis=None, old_reg=None, new_chassis=None):
    """
    Extracts OEM fields visually and generates cropped images for the UI.
    """
    logging.info(f"[UI] Processing OEM Visual: {pdf_path}")

    if not os.path.exists(pdf_path):
        logging.error("OEM PDF not found.")
        return []

    try:
        pil_img = _render_pdf_to_pil(pdf_path)
    except Exception as exc:
        logging.error(f"Failed to render OEM PDF {pdf_path}: {exc}")
        return []

    full_b64 = _pil_to_b64(pil_img)
    is_python_provider = (os.getenv("AI_PROVIDER", "").strip().upper() == "PYTHON")

    if is_python_provider:
        from .python_readers.reader_oem import try_extract_oem_fields
        python_data = try_extract_oem_fields(
            pdf_path,
            old_chassis=old_chassis or "",
            old_reg=old_reg or "",
            new_chassis=new_chassis or ""
        ) or {}

        coords = {
            "certificate_deposit_no": {"top": 10, "left": 0, "bottom": 30, "right": 100},
            "chassis_no":             {"top": 40, "left": 0, "bottom": 60, "right": 100}
        }

        extracted = {}
        for key, c in coords.items():
            if key in python_data:
                extracted[key] = {"text": python_data[key].get("text", ""), "line": python_data[key].get("line", 0), "crop": c}
            else:
                extracted[key] = {"text": "Not found", "line": 0, "crop": c}

        logging.info("[process_oem_visual] Python-only mode active — skipped AI visual call")
        return _pair_crops(pil_img, extracted)

    extracted, err_msg = _call_openai(
        full_b64,
        old_chassis=old_chassis,
        old_reg=old_reg,
        new_chassis=new_chassis
    )

    if not extracted:
        return _generate_mock_response(pil_img)

    return _pair_crops(pil_img, extracted)
