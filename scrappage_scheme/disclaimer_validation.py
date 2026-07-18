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
    # Fallback in case execution environment differs
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

# ── System Prompt (derived from cod_disclaimer_analyzer.html) ─────────────
DISCLAIMER_PROMPT = """You are an advanced document analysis AI. Your task is to read this "Customer Disclaimer for Loyalty/Scrappage Bonus through COD" document image line by line from top to bottom.

Extract ONLY the following 8 fields in exact order:
1. Dealership Name — printed at the top right of the document (company name near the logo, e.g. "Shivnath Motors (India) Pvt. Ltd.")
2. Document Title — the bold centered heading (e.g. "Customer Disclaimer for Loyalty/Scrappage Bonus through COD")
3. Customer Name — found in the first line of the declaration paragraph starting with "I,". Extract ONLY the name that appears between "I," and the next comma. Example: "I, Ankit Bhasin, residing at..." → "Ankit Bhasin"
4. Old Vehicle Details — from section 1, extract:
   - Registration Number (after "Registration Number:")
   - Vehicle Make (after "Vehicle Make:")
   - Vehicle Model (after "Vehicle Model")
5. New Vehicle Details — from section 2, extract:
   - New Vehicle Model (after "New Vehicle Model:")
   - Chassis Number (after "Chassis Number:")
   - Engine Number (after "Engine Number:")
6. Scrappage/Loyalty Benefit Amount — from section 4, extract the INR amount and the company name it was received from (e.g. "INR 20000.0 from the SHIVNATH MOTORS (I) PVT. LTD.")
7. Customer Signature — state whether a handwritten signature is visible near "Signature of Customer" at the bottom left, and report the printed name below it (e.g. "Handwritten signature present | Name: Ankit Bhasin")
8. Dealership Stamp & Seal — describe the circular stamp visible at the bottom right: company name printed on it, and whether an authorised signature is present on/near the stamp

For each field also return:
- The exact text found
- Which line number (approx) it appears on
- A crop bounding box as percentage of image width/height: {top%, left%, bottom%, right%}
  (IMPORTANT: Ensure coordinates accurately reflect the spatial location in the image. Do NOT hallucinate coordinates.)

Respond ONLY in this JSON format (no markdown, no extra text):
{
  "dealership_name":   {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "document_title":    {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "customer_name":     {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "old_vehicle_details":{"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "new_vehicle_details":{"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "benefit_amount":    {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "customer_signature":{"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "dealer_stamp":      {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}}
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
        return None

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
                    {"type": "text", "text": DISCLAIMER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{full_b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 1500,
        "temperature": 0.0,
    }

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logging.warning(f"Disclaimer vision retry {attempt + 1}/{max_retries}…")
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=90,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as exc:
            if attempt == max_retries - 1:
                logging.error(f"OpenAI disclaimer call failed after {max_retries} attempts: {exc}")
                return None
            if "429" in str(exc) or "Too Many Requests" in str(exc):
                time.sleep(5 * (2 ** attempt))
            else:
                time.sleep(2)
    return None

FIELD_MAPPING = {
    "dealership_name":    "Dealership Name",
    "document_title":     "Document Title",
    "customer_name":      "Customer Name",
    "old_vehicle_details":"Old Vehicle Details",
    "new_vehicle_details":"New Vehicle Details",
    "benefit_amount":    "Scrappage Benefit Amount",
    "customer_signature": "Customer Signature (Manual)",
    "dealer_stamp":       "Dealership Stamp & Seal"
}

FIELD_ORDER = [
    "dealership_name",
    "document_title",
    "customer_name",
    "old_vehicle_details",
    "new_vehicle_details",
    "benefit_amount",
    "customer_signature",
    "dealer_stamp"
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
            logging.error(f"Crop error for disclaimer field '{key}': {crop_err}")

        results.append({"field": label, "value": val, "crop_b64": crop_b64})

    return results

def _generate_mock_response(pil_img):
    """Return a placeholder result when the API is unavailable."""
    mock = {
        "dealership_name":    {"text": "API Error", "line": 1,  "crop": {"top": 0,   "left": 0, "bottom": 10, "right": 100}},
        "document_title":     {"text": "API Error", "line": 2,  "crop": {"top": 5,   "left": 0, "bottom": 15, "right": 100}},
        "customer_name":      {"text": "API Error", "line": 10, "crop": {"top": 10,  "left": 0, "bottom": 25, "right": 100}},
        "old_vehicle_details":{"text": "API Error", "line": 20, "crop": {"top": 20,  "left": 0, "bottom": 40, "right": 100}},
        "new_vehicle_details":{"text": "API Error", "line": 30, "crop": {"top": 35,  "left": 0, "bottom": 55, "right": 100}},
        "benefit_amount":     {"text": "API Error", "line": 40, "crop": {"top": 50,  "left": 0, "bottom": 70, "right": 100}},
        "customer_signature": {"text": "API Error", "line": 50, "crop": {"top": 70,  "left": 0, "bottom": 85, "right": 100}},
        "dealer_stamp":       {"text": "API Error", "line": 60, "crop": {"top": 80,  "left": 0, "bottom": 100, "right": 100}},
    }
    return _pair_crops(pil_img, mock)

# ── PUBLIC: validate_disclaimer (called by processor.py) ──────────────────
def check_model_match(portal_model, doc_model):
    if not portal_model or not doc_model:
        return False
    pm_clean = re.sub(r"[^a-zA-Z0-9\s]", "", portal_model.upper())
    dm_clean = re.sub(r"[^a-zA-Z0-9\s]", "", doc_model.upper())
    
    pm_words = [w for w in pm_clean.split() if len(w) >= 2]
    dm_words = dm_clean.split()
    
    abbrev_map = {
        "BOL": ["BOLERO"],
        "BOLERO": ["BOL"],
        "PUP": ["PICKUP", "PIKUP", "PIK-UP"],
        "PICKUP": ["PUP", "PIKUP", "PIK-UP"],
        "PIKUP": ["PUP", "PICKUP", "PIK-UP"],
        "MAX": ["MAXX"],
        "MAXX": ["MAX"],
        "HD": ["HEAVY", "DUTY"],
        "NEO": ["NEO"]
    }
    
    matches_all = True
    matches_any_major = False
    
    for pw in pm_words:
        word_found = False
        # Try direct/substring match first (with O/0 normalization for vehicle models)
        for dw in dm_words:
            pw_norm = pw.replace("O", "0")
            dw_norm = dw.replace("O", "0")
            if pw_norm in dw_norm or dw_norm in pw_norm:
                word_found = True
                break
        
        # Try abbreviation mapping
        if not word_found:
            alts = abbrev_map.get(pw, [])
            for alt in alts:
                for dw in dm_words:
                    if alt in dw or dw in alt:
                        word_found = True
                        break
                if word_found:
                    break
                    
        if word_found and len(pw) >= 3:
            matches_any_major = True
            
        if not word_found:
            matches_all = False
            
    # If it matched all words (even short ones), or if it matched at least one major identifying word (like SUPRO, SCORPIO, BOLERO)
    return matches_all or matches_any_major


# ── PUBLIC: validate_disclaimer (called by processor.py) ──────────────────
def validate_disclaimer(pdf_path, claim_details, old_vehicle_details, data_store):
    """
    Validates a Scrappage Disclaimer document.
    Returns (success: bool, message: str).
    """
    logging.info(f"Validating Scrappage Disclaimer: {pdf_path}")

    if not os.path.exists(pdf_path):
        logging.error("Disclaimer PDF not found.")
        return False, "Disclaimer PDF not found"

    # ── Fast path: Python text reader ────────────────────────────────────────
    from .python_readers.reader_disclaimer import try_extract_disclaimer_fields
    python_data = try_extract_disclaimer_fields(pdf_path) or {}

    extracted = None

    # Skip AI if Python extracted title/customer OR if the active provider is Python
    is_python_provider = (os.getenv("AI_PROVIDER", "").strip().upper() == "PYTHON")

    if is_python_provider:
        extracted = {}
        if python_data:
            for key, val in python_data.items():
                line_no = val.get("line", 0)
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
                    
                extracted[key] = {
                    "text": val.get("text", ""),
                    "line": line_no,
                    "crop": crop
                }
        
        # Fill in the visual fields with dummy PASS values since we are using Python-only mode
        extracted["dealer_stamp"] = {"text": "Present (Python mock)", "line": 0, "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}
        extracted["customer_signature"] = {"text": "Present (Python mock) | Name: Mock", "line": 0, "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}
        
        logging.info("[validate_disclaimer] Running in Python-only mode — skipped AI, visual fields mocked")

    if not extracted:
        try:
            pil_img = _render_pdf_to_pil(pdf_path)
        except Exception as exc:
            logging.error(f"Failed to render disclaimer {pdf_path}: {exc}")
            return False, f"Failed to load image: {exc}"
        full_b64 = _pil_to_b64(pil_img)
        extracted = _call_openai(full_b64)
        if not extracted:
            return False, "LLM Extraction Failed"

    # Merge Python-extracted text fields into AI result (Python is more reliable for text)
    if python_data and not is_python_provider:
        for key, py_val in python_data.items():
            if key in ("customer_signature", "dealer_stamp"):
                continue  # Never override visual fields with Python data
            if not extracted.get(key, {}).get("text"):
                # AI missed this field — use Python's value
                extracted[key] = {
                    "text": py_val.get("text", ""),
                    "line": py_val.get("line", 0),
                    "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}
                }

    # Persist extracted data for later reference
    if data_store:
        data_store.update_doc_data("disclaimer", extracted)

    # ── Validation rules ────────────────────────────────────────────────────
    issues = []

    # 1. Dealer stamp / seal must be present
    stamp_text = extracted.get("dealer_stamp", {}).get("text", "").lower()
    if "missing" in stamp_text or not stamp_text.strip() or "no stamp" in stamp_text:
        issues.append("Dealer stamp/seal is MISSING on the disclaimer")

    # 2. Customer signature must be present
    sig_text = extracted.get("customer_signature", {}).get("text", "").lower()
    if "missing" in sig_text or not sig_text.strip() or "no signature" in sig_text:
        issues.append("Customer signature is MISSING on the disclaimer")

    # 3. Customer name check
    cust_text = extracted.get("customer_name", {}).get("text", "").strip()
    claim_name_val = claim_details.get("Customer Name", "").strip()
    if not cust_text:
        issues.append("Customer name not found on disclaimer")
    elif claim_name_val:
        # Clean both names
        c1 = re.sub(r"[^A-Z0-9\s]", "", cust_text.upper()).strip()
        c2 = re.sub(r"[^A-Z0-9\s]", "", claim_name_val.upper()).strip()
        
        c2_words = [w for w in c2.split() if len(w) >= 3]
        word_match = False
        if c2_words and all(w in c1 for w in c2_words):
            word_match = True
            
        import difflib
        ratio = difflib.SequenceMatcher(None, c1, c2).ratio()
        
        if not (c2 in c1 or c1 in c2 or word_match or ratio >= 0.80):
            issues.append(
                f"Disclaimer customer name '{cust_text}' does not match claim customer '{claim_name_val}'"
            )

    # 4. Dealership name match
    dealer_name_val = ""
    for key in ["Dealer Name", "DealerName", "Dealer_Name", "Dealer"]:
        if key in claim_details:
            val = str(claim_details[key]).strip()
            if val and not val.isdigit() and val != "0":
                dealer_name_val = val
                break
    
    if not dealer_name_val:
        for k, v in claim_details.items():
            if "dealer" in k.lower() and "code" not in k.lower():
                val = str(v).strip()
                if val and not val.isdigit() and val != "0":
                    dealer_name_val = val
                    break
            
    doc_dealer_name = extracted.get("dealership_name", {}).get("text", "").strip()
    if not doc_dealer_name:
        issues.append("Dealership Name not found on disclaimer")
    elif dealer_name_val:
        status_dlr, score_dlr = compare_values_robust(doc_dealer_name, dealer_name_val)
        if not status_dlr.startswith("MATCH"):
            doc_words = [w for w in re.sub(r"[^a-zA-Z0-9\s]", "", doc_dealer_name.lower()).split() if len(w) > 2]
            portal_words = [w for w in re.sub(r"[^a-zA-Z0-9\s]", "", dealer_name_val.lower()).split() if len(w) > 2]
            ignore_suffixes = {"motors", "india", "pvt", "ltd", "auto", "limited", "private", "cars", "mahindra"}
            doc_words_filtered = [w for w in doc_words if w not in ignore_suffixes]
            portal_words_filtered = [w for w in portal_words if w not in ignore_suffixes]
            
            word_match = False
            if doc_words_filtered and portal_words_filtered:
                if any(w in portal_words_filtered for w in doc_words_filtered):
                    word_match = True
            
            if not word_match:
                issues.append(
                    f"Disclaimer dealership name '{doc_dealer_name}' does not match portal dealer '{dealer_name_val}'"
                )

    # 5. Old vehicle details (Registration number check)
    old_veh_text = extracted.get("old_vehicle_details", {}).get("text", "").strip()
    old_reg_val = ""
    for k, v in old_vehicle_details.items():
        if "reg" in k.lower():
            old_reg_val = str(v).strip()
            break
    if not old_reg_val:
        for k, v in claim_details.items():
            if "reg" in k.lower():
                old_reg_val = str(v).strip()
                break
                
    if not old_veh_text:
        issues.append("Old vehicle details not found on disclaimer")
    elif old_reg_val:
        clean_reg_val = re.sub(r"[^a-zA-Z0-9]", "", old_reg_val.upper())
        clean_doc_veh = re.sub(r"[^a-zA-Z0-9]", "", old_veh_text.upper())
        
        # Normalize 'O' to '0' and 'I' to '1' for OCR robustness
        clean_reg_val_norm = clean_reg_val.replace("O", "0").replace("I", "1")
        clean_doc_veh_norm = clean_doc_veh.replace("O", "0").replace("I", "1")
        
        if clean_reg_val_norm not in clean_doc_veh_norm:
            issues.append(
                f"Disclaimer old vehicle registration number does not match portal registration '{old_reg_val}'"
            )

    # 6. New vehicle details (Chassis number check)
    new_veh_text = extracted.get("new_vehicle_details", {}).get("text", "").strip()
    claim_chassis = claim_details.get("Chassis No", "").strip()
    if not new_veh_text:
        issues.append("New vehicle details not found on disclaimer")
    elif claim_chassis:
        match = find_chassis_in_text(new_veh_text, claim_chassis, match_last_8=True)
        if not match:
            issues.append(
                f"Disclaimer new vehicle chassis does not match claim chassis '{claim_chassis}' (Extracted: '{new_veh_text}')"
            )

    # 7. New vehicle model group check (with custom check_model_match logic)
    portal_model = ""
    for k, v in claim_details.items():
        if "model group" in k.lower() or "model_group" in k.lower():
            portal_model = str(v).strip()
            break
    if not portal_model:
        for k, v in claim_details.items():
            if "model" in k.lower():
                portal_model = str(v).strip()
                break

    if not new_veh_text:
        # Already appended
        pass
    elif portal_model:
        if not check_model_match(portal_model, new_veh_text):
            issues.append(
                f"Disclaimer new vehicle model does not match portal model group '{portal_model}' (Extracted: '{new_veh_text}')"
            )

    if issues:
        return False, "; ".join(issues)
    return True, "Disclaimer Validated"

# ── PUBLIC: process_disclaimer_visual (called by app_ui.py) ───────────────
def process_disclaimer_visual(pdf_path):
    """
    Extracts disclaimer fields visually and generates cropped images for the UI.
    Returns a list of dicts: [{field, value, crop_b64}, …]
    """
    logging.info(f"[UI] Processing Disclaimer Visual: {pdf_path}")

    if not os.path.exists(pdf_path):
        logging.error("Disclaimer PDF not found.")
        return []

    try:
        pil_img = _render_pdf_to_pil(pdf_path)
    except Exception as exc:
        logging.error(f"Failed to render disclaimer {pdf_path}: {exc}")
        return []

    full_b64 = _pil_to_b64(pil_img)
    is_python_provider = (os.getenv("AI_PROVIDER", "").strip().upper() == "PYTHON")

    if is_python_provider:
        from .python_readers.reader_disclaimer import try_extract_disclaimer_fields
        python_data = try_extract_disclaimer_fields(pdf_path) or {}

        coords = {
            "dealership_name":   {"top": 0,  "left": 60, "bottom": 15, "right": 100},
            "document_title":    {"top": 10, "left": 10, "bottom": 22, "right": 90},
            "customer_name":     {"top": 20, "left": 0,  "bottom": 35, "right": 100},
            "old_vehicle_details":{"top": 35, "left": 0,  "bottom": 50, "right": 100},
            "new_vehicle_details":{"top": 50, "left": 0,  "bottom": 68, "right": 100},
            "benefit_amount":    {"top": 68, "left": 0,  "bottom": 82, "right": 100},
            "customer_signature":{"top": 82, "left": 0,  "bottom": 100, "right": 50},
            "dealer_stamp":      {"top": 82, "left": 50, "bottom": 100, "right": 100},
        }

        extracted = {}
        for key, c in coords.items():
            if key in python_data:
                extracted[key] = {"text": python_data[key].get("text", ""), "line": python_data[key].get("line", 0), "crop": c}
            else:
                text = "Present (Python mock)" if key in ("customer_signature", "dealer_stamp") else "Not found"
                extracted[key] = {"text": text, "line": 0, "crop": c}

        logging.info("[process_disclaimer_visual] Python-only mode active — skipped AI visual call")
        return _pair_crops(pil_img, extracted)

    extracted = _call_openai(full_b64)

    if not extracted:
        return _generate_mock_response(pil_img)

    return _pair_crops(pil_img, extracted)
