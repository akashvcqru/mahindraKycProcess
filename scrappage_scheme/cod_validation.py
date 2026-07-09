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


# ── System Prompt for Transfer Certificate of Deposit (COD) ──────────────────
COD_PROMPT = """You are an advanced document analysis AI. Your task is to read this "TRANSFER CERTIFICATE OF DEPOSIT" document image line by line from top to bottom.

Extract ONLY the following 5 fields in exact order:
1. Certificate No — The certificate number printed at the top (e.g. "COD20260470DL7CC4465" after "Certificate No :")
2. Customer Name — The name(s) of the customer(s)/owner(s) mentioned in the document from top to bottom (e.g. "BHISMADEV DHRUA" or "RAKESH KUMAR")
3. Registration No — The vehicle registration number (e.g. "DL7CC4465" after "Vehicle Registration No")
4. Vehicle Make — The vehicle make found in the Vehicle Details table after "Make :" (e.g. "HERO HONDA MOTORS LTD")
5. Vehicle Model — The vehicle model found in the Vehicle Details table after "Model :" (e.g. "HONDA CITY")

For each field also return:
- The exact text found
- Which line number (approx) it appears on
- A crop bounding box as percentage of image width/height: {top%, left%, bottom%, right%}
  (IMPORTANT: Ensure coordinates accurately reflect the spatial location in the image. Do NOT hallucinate coordinates.)

Respond ONLY in this JSON format (no markdown, no extra text):
{
  "certificate_no": {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "customer_name":  {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "registration_no":{"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "vehicle_make":   {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "vehicle_model":  {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}}
}"""


def _render_pdf_to_pil(pdf_path):
    """Convert first page of PDF (or image file) to a PIL Image."""
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


def _call_openai(full_b64, max_retries=3):
    """Call OpenAI GPT-4o Vision and return the parsed JSON dict."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logging.error("OPENAI_API_KEY not found in environment.")
        return None, "OPENAI_API_KEY not found in environment."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": "gpt-5.5",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": COD_PROMPT},
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
            if attempt > 0:
                logging.warning(f"COD vision retry {attempt + 1}/{max_retries}…")
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            try:
                return json.loads(content), None
            except json.JSONDecodeError:
                logging.error(f"Failed to parse JSON. Raw content: {content}")
                return None, f"JSONDecodeError: OpenAI returned non-JSON text: {content[:100]}..."
        except Exception as exc:
            if attempt == max_retries - 1:
                logging.error(f"OpenAI COD call failed after {max_retries} attempts: {exc}")
                return None, f"OpenAI Error: {exc}"
            time.sleep(2)
    return None, "Max retries exceeded."


FIELD_MAPPING = {
    "certificate_no": "Certificate No",
    "customer_name":  "customer_name",  # Maps to custom signature emoji in app_ui.py
    "registration_no":"registration_number",  # Maps to registration emoji
    "vehicle_make":   "Vehicle Make",
    "vehicle_model":  "Vehicle Model"
}

FIELD_ORDER = [
    "certificate_no",
    "customer_name",
    "registration_no",
    "vehicle_make",
    "vehicle_model"
]


def _pair_crops(pil_img, extracted):
    """Crop the PIL image for every extracted field and return UI-ready list."""
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
            logging.error(f"Crop error for COD field '{key}': {crop_err}")

        results.append({"field": label, "value": val, "crop_b64": crop_b64})

    return results


def _generate_mock_response(pil_img):
    """Return a placeholder result when the API is unavailable."""
    mock = {
        "certificate_no": {"text": "API Error", "line": 5,  "crop": {"top": 10, "left": 5,  "bottom": 20, "right": 90}},
        "customer_name":  {"text": "API Error", "line": 15, "crop": {"top": 30, "left": 10, "bottom": 45, "right": 80}},
        "registration_no":{"text": "API Error", "line": 16, "crop": {"top": 30, "left": 50, "bottom": 45, "right": 90}},
        "vehicle_make":   {"text": "API Error", "line": 22, "crop": {"top": 45, "left": 10, "bottom": 55, "right": 45}},
        "vehicle_model":  {"text": "API Error", "line": 22, "crop": {"top": 45, "left": 50, "bottom": 55, "right": 90}}
    }
    return _pair_crops(pil_img, mock)


def get_val_by_fuzzy_key(d, keys):
    if not d:
        return None
    for k, v in d.items():
        for target in keys:
            if target.lower() in k.lower():
                return str(v).strip()
    return None


def clean_comp(v):
    return re.sub(r"[^A-Z0-9]", "", str(v).upper())


def check_substring_match(val1, val2):
    if not val1 or not val2:
        return False
    c1 = clean_comp(val1)
    c2 = clean_comp(val2)
    return c1 in c2 or c2 in c1


_PDF_TEXT_CACHE = {}

def get_pdf_text(pdf_path):
    if pdf_path in _PDF_TEXT_CACHE:
        return _PDF_TEXT_CACHE[pdf_path]
        
    text = ""
    try:
        doc = fitz.open(pdf_path)
        text = "".join(page.get_text() for page in doc)
        if len(text.strip()) < 10:
            logging.info(f"PDF {pdf_path} has no embedded text. Running OCR for fallback verification...")
            try:
                import easyocr
                import numpy as np
                from PIL import Image
                import io
                
                reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                pix = doc[0].get_pixmap(dpi=150)
                png_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
                img_array = np.array(pil_img)
                
                ocr_results = reader.readtext(img_array, detail=0)
                text = " ".join(ocr_results)
            except Exception as ocr_err:
                logging.warning(f"OCR failed for {pdf_path} in helper: {ocr_err}")
    except Exception as e:
        logging.error(f"Error reading PDF {pdf_path}: {e}")
        
    _PDF_TEXT_CACHE[pdf_path] = text
    return text


def check_value_in_pdf(pdf_path, expected_value, keep_spaces=False):
    if not expected_value:
        return False
    try:
        full_text = get_pdf_text(pdf_path)
        if keep_spaces:
            full_text_clean = re.sub(r"[^A-Z0-9\s]", "", full_text.upper())
            val_clean = re.sub(r"[^A-Z0-9\s]", "", str(expected_value).upper())
        else:
            full_text_clean = re.sub(r"[^A-Z0-9]", "", full_text.upper())
            val_clean = re.sub(r"[^A-Z0-9]", "", str(expected_value).upper())
            
        if not val_clean:
            return False
        return val_clean in full_text_clean
    except Exception as exc:
        logging.error(f"Failed to read full text from PDF {pdf_path}: {exc}")
        return False


def validate_cod(pdf_path, claim_details, old_vehicle_details, data_store):
    """
    Validates a Transfer Certificate of Deposit (COD) document.
    Returns (success: bool, message: str).
    """
    logging.info(f"Validating Transfer COD: {pdf_path}")

    if not os.path.exists(pdf_path):
        logging.error("COD PDF not found.")
        return False, "COD PDF not found"

    try:
        pil_img = _render_pdf_to_pil(pdf_path)
    except Exception as exc:
        logging.error(f"Failed to render COD {pdf_path}: {exc}")
        return False, f"Failed to load image: {exc}"

    full_b64 = _pil_to_b64(pil_img)
    extracted, err_msg = _call_openai(full_b64)

    if not extracted:
        return False, f"LLM Extraction Failed: {err_msg}"

    # Persist extracted data for later reference
    if data_store:
        data_store.update_doc_data("cod", extracted)

    issues = []

    # 1. Certificate No Check (Verify it matches old vehicle Chassis Number / COD certificate number from portal)
    extracted_cert = extracted.get("certificate_no", {}).get("text", "").strip()
    web_old_chassis = get_val_by_fuzzy_key(old_vehicle_details, ["Chassis No", "Chassis Number"]) or \
                      get_val_by_fuzzy_key(claim_details, ["Chassis No", "Chassis Number"])
    
    if web_old_chassis and web_old_chassis.upper().strip() not in ("OTHERS", "OTHER", "ANY OTHER"):
        if not extracted_cert:
            if not check_value_in_pdf(pdf_path, web_old_chassis):
                issues.append(
                    f"COD Certificate No '{web_old_chassis}' not found in COD document"
                )
        else:
            if not check_substring_match(web_old_chassis, extracted_cert):
                if not check_value_in_pdf(pdf_path, web_old_chassis):
                    issues.append(
                        f"COD Certificate No '{extracted_cert}' does not match expected old chassis '{web_old_chassis}'"
                    )
    else:
        # Fallback to check against Registration No if Chassis No is not specified or is OTHERS
        web_old_reg = get_val_by_fuzzy_key(old_vehicle_details, ["Reg. No", "Reg No", "Registration No", "Registration"]) or \
                      get_val_by_fuzzy_key(claim_details, ["Reg. No", "Reg No", "Registration No", "Registration"])
        if web_old_reg and web_old_reg.upper().strip() not in ("OTHERS", "OTHER", "ANY OTHER"):
            if not extracted_cert:
                if not check_value_in_pdf(pdf_path, web_old_reg):
                    issues.append("Certificate number not found on COD document")
            else:
                if not check_substring_match(web_old_reg, extracted_cert):
                    if not check_value_in_pdf(pdf_path, web_old_reg):
                        issues.append(
                            f"COD Certificate No '{extracted_cert}' does not match expected old vehicle registration '{web_old_reg}'"
                        )

    # 2. Customer Name Check (Verify customer name is present in the document from top to bottom)
    extracted_cust_text = extracted.get("customer_name", {}).get("text", "").strip()
    portal_cust_name = claim_details.get("Customer Name", "").strip()
    
    if not portal_cust_name:
        # Fallback to owner name from old vehicle
        portal_cust_name = get_val_by_fuzzy_key(old_vehicle_details, ["Customer Name", "Owner Name", "Name"]) or ""

    if portal_cust_name:
        p_clean = re.sub(r"[^A-Z0-9\s]", "", portal_cust_name.upper())
        doc_clean = re.sub(r"[^A-Z0-9\s]", "", extracted_cust_text.upper())
        
        name_found = p_clean in doc_clean
        p_words = [w for w in p_clean.split() if len(w) >= 3]
        if not name_found:
            # Word-based fallback for name matching (all words length >= 3 must be in extracted text)
            if p_words and all(w in doc_clean for w in p_words):
                name_found = True
        
        # Fallback 2: Check if portal customer name is present anywhere in the full text of the COD PDF
        if not name_found:
            try:
                full_text = get_pdf_text(pdf_path)
                full_text_clean = re.sub(r"[^A-Z0-9\s]", "", full_text.upper())
                if p_clean in full_text_clean:
                    name_found = True
                elif p_words and all(w in full_text_clean for w in p_words):
                    name_found = True
            except Exception as exc:
                logging.error(f"Failed to read full text from COD PDF for name verification: {exc}")

        if not name_found:
            issues.append(
                f"Portal customer name '{portal_cust_name}' not found from top to bottom in COD document (Extracted: '{extracted_cust_text}')"
            )

    # 3. Registration No Check
    extracted_reg = extracted.get("registration_no", {}).get("text", "").strip()
    web_old_reg = get_val_by_fuzzy_key(old_vehicle_details, ["Reg. No", "Reg No", "Registration No", "Registration"]) or \
                  get_val_by_fuzzy_key(claim_details, ["Reg. No", "Reg No", "Registration No", "Registration"])
    
    if not extracted_reg:
        if web_old_reg and check_value_in_pdf(pdf_path, web_old_reg):
            pass
        else:
            issues.append("Registration Number not found on COD document")
    elif web_old_reg:
        if not check_substring_match(web_old_reg, extracted_reg):
            if not check_value_in_pdf(pdf_path, web_old_reg):
                issues.append(
                    f"COD Registration No '{extracted_reg}' does not match expected old vehicle registration '{web_old_reg}'"
                )



    if issues:
        return False, "; ".join(issues)
    return True, "COD Validated"


def process_cod_visual(pdf_path):
    """
    Extracts COD fields visually and generates cropped images for the UI.
    Returns a list of dicts: [{field, value, crop_b64}, …]
    """
    logging.info(f"[UI] Processing Transfer COD Visual: {pdf_path}")

    if not os.path.exists(pdf_path):
        logging.error("COD PDF not found.")
        return []

    try:
        pil_img = _render_pdf_to_pil(pdf_path)
    except Exception as exc:
        logging.error(f"Failed to render COD {pdf_path}: {exc}")
        return []

    full_b64 = _pil_to_b64(pil_img)
    extracted, err_msg = _call_openai(full_b64)

    if not extracted:
        return _generate_mock_response(pil_img)

    return _pair_crops(pil_img, extracted)
