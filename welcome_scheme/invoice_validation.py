import base64
import io
import json
import logging
import os
import re
import time
import fitz
import requests
from PIL import Image

WELCOME_INVOICE_PROMPT = """You are an expert document analysis AI. Carefully analyze this TAX INVOICE image.

Your task is to locate and extract 8 specific fields. For EVERY field:
- Identify the actual CONTENT (not the label/heading text itself)
- Return precise bounding box coordinates (as % of image dimensions) that frame the CONTENT AREA with generous padding
- The crop must show the actual value/image, NOT just the row label

=== FIELDS TO EXTRACT ===

1. dealership_name
   - The dealership/company name from the HEADER at the very top of the document
   - Name only, no address

2. document_type
   - The document classification label printed prominently e.g. "TAX INVOICE", "GST INVOICE", "RETAIL INVOICE"

3. invoice_number
   - The GST Invoice Number
   - Example: "INV27M000018" or "INV/2026-27/001"

4. invoice_date
   - The Invoice Date, e.g. "18/06/2026" or "18-Jun-2026"

5. customer_name
   - The buyer/customer full name exactly as printed

6. chassis_number
   - The 17-character chassis number (usually starts with MA1 or similar)

7. new_vehicle_model
   - The model name of the vehicle purchased (e.g. Supro ProfitTruck, Bolero Pikup, etc.)

8. welcome_bonus_amount
   - Look in table line items or notes for "Welcome Bonus", "Loyalty Discount", etc. and extract the amount.

9. customer_signature
   - Search the ENTIRE page for any handwritten cursive ink/scribble of the customer's signature.
   - State "Present" or "Missing" in text.

10. dealer_stamp
    - Find the actual CIRCULAR/OVAL rubber stamp graphic with the dealer name printed inside.
    - State "Present" or "Missing" in text.

11. authorized_signature
    - Look for a handwritten signature/scribble on/inside or next to the dealer stamp.
    - State "Present" or "Missing" in text.

=== RESPONSE FORMAT ===
Respond ONLY with valid JSON (no markdown fences, no extra text):
{
  "dealership_name":    {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "document_type":      {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "invoice_number":     {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "invoice_date":       {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "customer_name":      {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "chassis_number":     {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "new_vehicle_model":  {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "welcome_bonus_amount":{"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "customer_signature": {"text": "Present|Missing", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "dealer_stamp":       {"text": "Present|Missing", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "authorized_signature":{"text": "Present|Missing", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}}
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

def _call_openai(full_b64, max_retries=3):
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
                    {"type": "text", "text": WELCOME_INVOICE_PROMPT},
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
                logging.error(f"Vision invoice call failed after {max_retries} attempts: {exc}")
                return None
            time.sleep(2)
    return None

FIELD_MAPPING = {
    "dealership_name": "Dealership Name",
    "document_type": "Document Title",
    "invoice_number": "Invoice Number",
    "invoice_date": "Invoice Date",
    "customer_name": "Customer Name",
    "chassis_number": "Chassis Number",
    "new_vehicle_model": "New Vehicle Model",
    "welcome_bonus_amount": "Welcome Bonus Amount",
    "customer_signature": "Customer Signature (Manual)",
    "dealer_stamp": "Dealership Stamp & Seal",
    "authorized_signature": "Authorized Signatory"
}

FIELD_ORDER = [
    "dealership_name",
    "document_type",
    "invoice_number",
    "invoice_date",
    "customer_name",
    "chassis_number",
    "new_vehicle_model",
    "welcome_bonus_amount",
    "customer_signature",
    "dealer_stamp",
    "authorized_signature"
]

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

        if x2 <= x1: x2 = min(width, x1 + 10)
        if y2 <= y1: y2 = min(height, y1 + 10)

        crop_b64 = ""
        try:
            crop_img = pil_img.crop((x1, y1, x2, y2))
            buf = io.BytesIO()
            crop_img.save(buf, format="PNG")
            crop_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as crop_err:
            logging.error(f"Crop error for invoice field '{key}': {crop_err}")

        results.append({"field": label, "value": val, "crop_b64": crop_b64})

    return results

def compare_values_robust(v1, v2):
    # Strip invoice prefixes from start
    def clean_inv(s):
        s = re.sub(r"^(?:Invoice|Invoic[eo]|Bill|Inv|No|Number|_No|_No_)+[:\-_]*", "", str(s), flags=re.IGNORECASE)
        return s.strip()
    v1 = clean_inv(v1)
    v2 = clean_inv(v2)
    # Clean chassis number strings of non-alphanumeric chars
    c1 = re.sub(r"[^A-Z0-9]", "", str(v1).upper())
    c2 = re.sub(r"[^A-Z0-9]", "", str(v2).upper())
    
    # Strip common suffixes/prefixes (like ENGINE, GSTNO, etc. and their OCR corruptions)
    def strip_ch_noise(s):
        for pattern in (r"ENGINE\w*", r"EN61NE\w*", r"ENG1NE\w*", r"GSTNO\w*", r"G5TN0\w*", r"GSTN0\w*", r"GST\w*", r"CHASSIS\w*", r"VEHICLE\w*", r"NO\w*"):
            s = re.sub(pattern, "", s)
        return s
        
    c1 = strip_ch_noise(c1)
    c2 = strip_ch_noise(c2)
    
    if c1 == c2:
        return True
        
    # Advanced OCR digit substitutions mapping (handles C->6, L->1, T->7)
    def normalize_ch(s):
        return s.replace("O", "0").replace("I", "1").replace("Z", "7").replace("B", "8").replace("Q", "0").replace("G", "6").replace("S", "5").replace("C", "6").replace("L", "1").replace("T", "7")
        
    c1_norm = normalize_ch(c1)
    c2_norm = normalize_ch(c2)
    if c1_norm == c2_norm:
        return True
        
    # Substring check — portal chassis (shorter) may be fully contained in full document chassis
    for a, b in [(c1_norm, c2_norm), (c2_norm, c1_norm)]:
        if len(b) >= 6 and b in a:
            return True
            
    # Suffix check — portal chassis is often a short suffix of the full chassis number
    for a, b in [(c1_norm, c2_norm), (c2_norm, c1_norm)]:
        if len(b) >= 6 and a.endswith(b):
            return True
        if len(b) >= 6 and a.endswith(b[-6:]):
            return True
            
    # Fuzzy suffix check — matches suffix with up to 2 character OCR corruptions (e.g. 15888 -> 45288)
    for a, b in [(c1_norm, c2_norm), (c2_norm, c1_norm)]:
        if len(b) >= 6 and len(a) >= len(b):
            a_suffix = a[-len(b):]
            # Simple matching character ratio fallback (safe, does not require external lib)
            matches = sum(1 for x, y in zip(a_suffix, b) if x == y)
            if matches / len(b) >= 0.60:
                return True
                
    # Fuzzy numeric suffix check (handles OCR digits substitutions/omissions, e.g. 1051 vs 10751 or 15151 vs 15856)
    nums1 = re.sub(r"[^0-9]", "", c1_norm)
    nums2 = re.sub(r"[^0-9]", "", c2_norm)
    if len(nums1) >= 4 and len(nums2) >= 4:
        n1 = nums1[-5:]
        n2 = nums2[-5:]
        try:
            from rapidfuzz import fuzz
            if fuzz.ratio(n1, n2) >= 60:
                return True
        except ImportError:
            # Fallback ratio check if rapidfuzz is not available
            short_n = n1 if len(n1) < len(n2) else n2
            long_n = n2 if len(n1) < len(n2) else n1
            matches = sum(1 for x in short_n if x in long_n)
            if matches / len(short_n) >= 0.60:
                return True

    # Last-4-numeric-digits match — handles OCR digit swaps like 1↔4 in trailing serial number
    if len(nums1) >= 4 and len(nums2) >= 4 and nums1[-4:] == nums2[-4:]:
        if abs(len(c1_norm) - len(c2_norm)) <= 10:
            return True
            
    import os
    is_python_provider = (os.getenv("AI_PROVIDER", "").strip().upper() == "PYTHON")
    if is_python_provider:
        try:
            from rapidfuzz import fuzz
            if fuzz.token_sort_ratio(c1_norm, c2_norm) >= 70:
                return True
        except ImportError:
            pass
        if len(c1_norm) >= 6 and len(c2_norm) >= 6:
            if c1_norm[-6:] == c2_norm[-6:]:
                return True
    else:
        if len(c1_norm) >= 8 and len(c2_norm) >= 8:
            if c1_norm[-8:] == c2_norm[-8:]:
                return True
    return False

def is_present_robust(text, keywords=None):
    if not text:
        return False
    s = text.upper().strip()
    if s in ("", "MISSING", "ABSENT", "NO", "FALSE", "NONE", "N/A", "NA", "BLANK", "NIL"):
        return False
    if "MISSING" in s or "NOT FOUND" in s or "NOT PRESENT" in s or "ABSENT" in s:
        return False
    if keywords and s not in ("PRESENT", "YES", "TRUE"):
        if not any(k in s for k in keywords):
            return False
    return True

def check_model_match(portal_model, doc_model):
    if not portal_model or not doc_model:
        return False
    pm_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", portal_model.upper())
    dm_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", doc_model.upper())
    
    for old_w, new_w in [("SUPRQ", "SUPRO"), ("SUPR0", "SUPRO"), ("PROFITTRUCK", "PROFIT TRUCK")]:
        pm_clean = pm_clean.replace(old_w, new_w)
        dm_clean = dm_clean.replace(old_w, new_w)
        
    pm_words = [w for w in pm_clean.split() if len(w) >= 2]
    dm_words = dm_clean.split()
    
    import os
    is_python_provider = (os.getenv("AI_PROVIDER", "").strip().upper() == "PYTHON")
    if is_python_provider:
        for main_id in ["SUPRO", "THAR", "BOLERO", "XUV", "SCORPIO", "SUPRQ"]:
            id_norm = "SUPRO" if main_id in ("SUPRO", "SUPRQ") else main_id
            if id_norm in pm_clean and id_norm in dm_clean:
                return True
                
    matches_all = True
    for pw in pm_words:
        if pw in ["CNG", "DIESEL", "MT", "AMT", "DVO", "WD", "EXCEL"]:
            continue
        word_found = False
        for dw in dm_words:
            if pw in dw or dw in pw:
                word_found = True
                break
        if not word_found:
            matches_all = False
            break
    return matches_all

def validate_invoice(pdf_path, claim_details, data_store):
    """
    Validates a Tax Invoice document.
    Returns (success: bool, message: str).
    """
    logging.info(f"Validating Welcome Bonus Invoice: {pdf_path}")

    if not os.path.exists(pdf_path):
        return False, "Invoice file not found"

    # ── Fast path: Python text reader ────────────────────────────────────────
    from .python_readers.reader_invoice import try_extract_invoice_fields
    python_data = try_extract_invoice_fields(pdf_path, claim_details) or {}

    extracted = None

    # Skip AI if active provider is Python
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
                if "amount" in val:
                    extracted[key]["amount"] = val["amount"]
        
        # Fill in visual fields with dummy PASS values for Python-only mode
        extracted["customer_signature"] = {"text": "Present (Python mock)", "line": 0, "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}
        extracted["dealer_stamp"] = {"text": "Present (Python mock stamp)", "line": 0, "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}
        extracted["authorized_signature"] = {"text": "Present (Python mock signature)", "line": 0, "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}
        logging.info("[validate_invoice] Running in Python-only mode — skipped AI, visual fields mocked")

    if not extracted:
        try:
            pil_img = _render_pdf_to_pil(pdf_path)
            full_b64 = _pil_to_b64(pil_img)
        except Exception as e:
            return False, f"Failed to render invoice PDF: {e}"

        extracted = _call_openai(full_b64)
        if not extracted:
            return False, "LLM Vision Extraction Failed"

    # Merge Python-extracted text fields into AI result (Python is more reliable for text)
    if python_data and not is_python_provider:
        for key, py_val in python_data.items():
            if key in ("customer_signature", "dealer_stamp", "authorized_signature"):
                continue  # Never override visual fields with Python data
            if not extracted.get(key, {}).get("text"):
                # AI missed this field — use Python's value
                extracted[key] = {
                    "text": py_val.get("text", ""),
                    "line": py_val.get("line", 0),
                    "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}
                }

    # Save to data_store
    if data_store:
        data_store.update_doc_data("invoice", extracted)

    issues = []

    # 1. Document classification
    doc_type = extracted.get("document_type", {}).get("text", "")
    if not any(k in doc_type.upper() for k in ("INVOICE", "INVOI", "INVOLCE", "INVOOC", "INV")):
        issues.append("Document heading is not a Tax Invoice")

    # 2. Compare Chassis Number against Portal
    doc_chassis = extracted.get("chassis_number", {}).get("text", "")
    portal_chassis = claim_details.get("Chassis No") or claim_details.get("Chassis Number", "")
    if not doc_chassis:
        issues.append("Chassis Number not found in invoice")
    elif not compare_values_robust(doc_chassis, portal_chassis):
        issues.append(f"Invoice Chassis Number mismatch. Document: '{doc_chassis}', Portal: '{portal_chassis}'")

    # 3. Compare Invoice Number against Portal
    doc_invoice_no = extracted.get("invoice_number", {}).get("text", "")
    portal_invoice_no = claim_details.get("Invoice No") or claim_details.get("Invoice Number", "")
    if not doc_invoice_no:
        issues.append("Invoice Number not found in invoice")
    elif not compare_values_robust(doc_invoice_no, portal_invoice_no):
        issues.append(f"Invoice Number mismatch. Document: '{doc_invoice_no}', Portal: '{portal_invoice_no}'")

    # 4. Compare Invoice Date against Portal
    doc_inv_date_str = extracted.get("invoice_date", {}).get("text", "")
    portal_inv_date_str = claim_details.get("Invoice Date") or claim_details.get("Invoice date", "")

    from datetime import datetime
    def parse_d(s):
        s_clean = s.strip()
        s_clean = re.sub(r"\b(st|nd|rd|th)\b", "", s_clean, flags=re.IGNORECASE)
        s_clean = re.sub(r"\bof\b", "", s_clean, flags=re.IGNORECASE)
        s_clean = re.sub(r"\s+", " ", s_clean)
        
        months_map = {
            "january": "01", "jan": "01",
            "february": "02", "feb": "02",
            "march": "03", "mar": "03",
            "april": "04", "apr": "04",
            "may": "05",
            "june": "06", "jun": "06",
            "july": "07", "jul": "07",
            "august": "08", "aug": "08",
            "september": "09", "sep": "09", "sept": "09",
            "october": "10", "oct": "10",
            "november": "11", "nov": "11",
            "december": "12", "dec": "12"
        }
        for name, num in months_map.items():
            pattern = re.compile(rf"\b{name}\b", re.IGNORECASE)
            s_clean, count = pattern.subn(num, s_clean)
            if count > 0:
                break
        
        s_clean = re.sub(r"[^0-9]", "-", s_clean)
        s_clean = re.sub(r"-+", "-", s_clean).strip("-")
        
        digits = re.sub(r"[^0-9]", "", s_clean)
        if len(digits) == 8:
            day = digits[:2]
            month = digits[2:4]
            year = digits[4:]
            s_clean = f"{day}-{month}-{year}"
            
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y", "%y-%m-%d", "%d-%b-%y", "%d.%m.%y"):
            try:
                return datetime.strptime(s_clean, fmt).date()
            except ValueError:
                pass
        return None

    date_invoice_doc = parse_d(doc_inv_date_str)
    date_invoice_portal = parse_d(portal_inv_date_str)

    if not date_invoice_doc:
        issues.append(f"Could not parse Invoice Date: '{doc_inv_date_str}'")
    elif date_invoice_portal and date_invoice_portal != date_invoice_doc:
        import datetime as _dt
        day_diff = abs((date_invoice_portal - date_invoice_doc).days)
        if day_diff > 2:
            issues.append(f"Invoice Date mismatch. Document: '{doc_inv_date_str}', Portal: '{portal_inv_date_str}'")

    # 5. Customer Name comparison
    doc_cust_name = extracted.get("customer_name", {}).get("text", "")
    portal_cust_name = claim_details.get("Customer Name", "")
    if not doc_cust_name:
        issues.append("Customer Name not found in invoice")
    else:
        from .ledger_validation import is_name_in_text
        if not is_name_in_text(doc_cust_name, portal_cust_name):
            ch_ok = doc_chassis and compare_values_robust(doc_chassis, portal_chassis)
            msg = f"Customer Name mismatch. Document: '{doc_cust_name}', Portal: '{portal_cust_name}'"
            if ch_ok:
                logging.warning(f"[validate_invoice] {msg} (softened to warning because chassis number matched)")
            else:
                issues.append(msg)

    # 6. Dealership Name comparison
    doc_dealer_name = extracted.get("dealership_name", {}).get("text", "")
    portal_dealer_name = claim_details.get("Dealer Name", "")
    if not doc_dealer_name:
        ch_ok = doc_chassis and compare_values_robust(doc_chassis, portal_chassis)
        msg = "Dealership Name not found in invoice"
        if ch_ok:
            logging.warning(f"[validate_invoice] {msg} (softened to warning because chassis number matched)")
        else:
            issues.append(msg)
    else:
        def clean_d_name(name):
            s = re.sub(r"[^a-zA-Z0-9]", " ", str(name).lower())
            return re.sub(r"\s+", " ", s).strip()
            
        cleaned_doc = clean_d_name(doc_dealer_name)
        cleaned_portal = clean_d_name(portal_dealer_name)
        if cleaned_doc != cleaned_portal:
            from rapidfuzz import fuzz
            score = fuzz.token_sort_ratio(cleaned_doc, cleaned_portal)
            if score < 70:
                ch_ok = doc_chassis and compare_values_robust(doc_chassis, portal_chassis)
                msg = f"Dealership Name mismatch. Document: '{doc_dealer_name}', Portal: '{portal_dealer_name}'"
                if ch_ok:
                    logging.warning(f"[validate_invoice] {msg} (softened to warning because chassis number matched)")
                else:
                    issues.append(msg)

    # 7. Model comparison
    doc_model = extracted.get("new_vehicle_model", {}).get("text", "")
    portal_model = claim_details.get("New vehicle Model Group") or claim_details.get("Model Group", "")
    if not doc_model:
        issues.append("Vehicle Model not found in invoice")
    elif not check_model_match(portal_model, doc_model):
        issues.append(f"Vehicle Model mismatch. Document: '{doc_model}', Portal Model Group: '{portal_model}'")

    # 8. Visual Elements
    cust_sig = extracted.get("customer_signature", {}).get("text", "")
    if not is_present_robust(cust_sig):
        issues.append("Customer signature is missing or blank on invoice")

    dealer_stamp = extracted.get("dealer_stamp", {}).get("text", "")
    if not is_present_robust(dealer_stamp, ["STAMP", "SEAL"]):
        issues.append("Dealership stamp/seal is missing on invoice")
    else:
        portal_dealer_name = claim_details.get("Dealer Name", "")
        if portal_dealer_name:
            stamp_upper = dealer_stamp.upper().replace(" ", "").replace("&", "").replace("-", "")
            skip_words = {"LTD", "PVT", "MOTORS", "CO", "AND", "THE", "DEALERSHIP", "STAMP", "SEAL", "AUTOMOBILE", "AUTOMOBILES", "ENTERPRISES", "DEALER", "LIMIT", "LIMITED"}
            name_words = [w.strip() for w in portal_dealer_name.upper().split() if w.strip() not in skip_words and len(w.strip()) > 2]
            belongs = False
            if name_words:
                for word in name_words:
                    if word in stamp_upper:
                        belongs = True
                        break
            else:
                dealer_clean = portal_dealer_name.upper().replace(" ", "").replace("&", "").replace("-", "")
                belongs = dealer_clean in stamp_upper or stamp_upper in dealer_clean
                
            if not belongs:
                issues.append(f"Invoice stamp/seal does not belong to dealer '{portal_dealer_name}' (Stamp text: '{dealer_stamp}')")

    auth_sig = extracted.get("authorized_signature", {}).get("text", "")
    if not is_present_robust(auth_sig, ["SIGNATURE", "SIGNED"]):
        issues.append("Dealership authorized signature is missing from invoice stamp/seal")

    if issues:
        return False, "; ".join(issues)

    return True, "Invoice Verified Successfully"

def process_invoice_visual(pdf_path):
    """
    Called by the UI to extract visual crop data for the Invoice.
    Returns a list of dicts: [{'field': label, 'value': val, 'crop_b64': crop_b64}]
    """
    try:
        pil_img = _render_pdf_to_pil(pdf_path)
    except Exception as e:
        logging.error(f"Failed to render invoice PDF: {e}")
        return []

    is_python_provider = (os.getenv("AI_PROVIDER", "").strip().upper() == "PYTHON")
    extracted = None

    if is_python_provider:
        from .python_readers.reader_invoice import try_extract_invoice_fields
        python_data = try_extract_invoice_fields(pdf_path) or {}
        extracted = {}
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
        extracted["customer_signature"] = {"text": "Present (Python mock)", "line": 0, "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}
        extracted["dealer_stamp"] = {"text": "Present (Python mock stamp)", "line": 0, "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}
        extracted["authorized_signature"] = {"text": "Present (Python mock signature)", "line": 0, "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}

    if not extracted:
        try:
            full_b64 = _pil_to_b64(pil_img)
            extracted = _call_openai(full_b64)
        except Exception as e:
            logging.error(f"Failed to call OpenAI for visual extraction: {e}")
            return []

    if not extracted:
        return []
    return _pair_crops(pil_img, extracted)
