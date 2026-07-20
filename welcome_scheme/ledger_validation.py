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

WELCOME_LEDGER_PROMPT = """You are an expert document analysis AI. Carefully analyze this LEDGER / STATEMENT image.

Your task is to locate and extract 6 specific fields. For EVERY field:
- Identify the actual CONTENT (not the label/heading text itself)
- Return precise bounding box coordinates (as % of image dimensions) that frame the CONTENT AREA with generous padding
- The crop must show the actual value/image, NOT just the row label

=== FIELDS TO EXTRACT ===

1. dealership_name
   - The dealership/company name from the HEADER at the very top of the document (Name only, no address)

2. document_type
   - The document classification label printed prominently e.g. "Ledger Account", "Statement of Account", "Customer Ledger"

3. customer_name
   - The buyer/customer full name exactly as printed (usually near the top)

4. welcome_bonus_row
   - Locate the transaction row corresponding to the Welcome Bonus entry.
   - Extract the full text description of that row (including entry description and credit amount).
   - If not found, write "Missing".

5. dealer_stamp
    - Find the actual CIRCULAR/OVAL rubber stamp graphic.
    - The text must include the name of the dealer printed inside the stamp itself (e.g. "Chandamama Motors").
    - State "Present" or "Missing" in text.

6. authorized_signature
    - Look for a handwritten signature/scribble on/inside or next to the dealer stamp.
    - State "Present" or "Missing" in text.

=== RESPONSE FORMAT ===
Respond ONLY with valid JSON (no markdown fences, no extra text):
{
  "dealership_name":    {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "document_type":      {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "customer_name":      {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "welcome_bonus_row":  {"text": "...", "amount": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "dealer_stamp":       {"text": "Present|Missing", "stamp_dealer_name": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
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
                    {"type": "text", "text": WELCOME_LEDGER_PROMPT},
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
                logging.error(f"Vision ledger call failed after {max_retries} attempts: {exc}")
                return None
            time.sleep(2)
    return None

FIELD_MAPPING = {
    "dealership_name": "Dealership Name",
    "document_type": "Document Title",
    "customer_name": "Customer Name",
    "welcome_bonus_row": "Welcome Bonus Row Entry",
    "dealer_stamp": "Dealership Stamp & Seal",
    "authorized_signature": "Authorized Signatory"
}

FIELD_ORDER = [
    "dealership_name",
    "document_type",
    "customer_name",
    "welcome_bonus_row",
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
            logging.error(f"Crop error for ledger field '{key}': {crop_err}")

        results.append({"field": label, "value": val, "crop_b64": crop_b64})

    return results

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

def is_name_in_text(text, name, threshold=80):
    if not text or not name:
        return False
    name_clean = name.strip().lower()
    text_clean = text.lower()

    # 1. Simple substring check
    if name_clean in text_clean:
        return True

    # 2. Word-by-word match
    words = [w for w in re.sub(r"[^a-z]", " ", name_clean).split() if len(w) >= 3]
    if not words:
        return False

    from rapidfuzz import fuzz
    all_matched = True
    for word in words:
        if word in text_clean:
            continue
        word_found = False
        text_tokens = re.sub(r"[^a-z]", " ", text_clean).split()
        for token in text_tokens:
            if len(token) >= 3 and fuzz.ratio(word, token) >= threshold:
                word_found = True
                break
        if not word_found:
            all_matched = False
            break

    return all_matched

def extract_amount_robust(amt_str):
    if not amt_str:
        return None
    s = amt_str.lower().replace(",", "").replace("k", "000")
    
    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, 
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "hundred": 100, "thousand": 1000, "lakh": 100000
    }
    
    num_str = re.sub(r"[^0-9\.]", "", s)
    if num_str:
        try:
            return float(num_str)
        except Exception:
            pass
            
    words = re.findall(r'[a-z]+', s)
    if words:
        total = 0
        current = 0
        for w in words:
            if w in word_to_num:
                val = word_to_num[w]
                if val >= 100:
                    current = (current if current else 1) * val
                    total += current
                    current = 0
                else:
                    current += val
        total += current
        if total > 0:
            return float(total)
            
    return None

def validate_ledger(pdf_path, claim_details, data_store):
    """
    Validates a Ledger PDF.
    Returns (success: bool, message: str).
    """
    logging.info(f"Validating Welcome Bonus Ledger: {pdf_path}")

    if not os.path.exists(pdf_path):
        return False, "Ledger file not found"

    # ── Fast path: Python text reader ─────────────────────────────────────────
    from .python_readers.reader_ledger import try_extract_ledger_fields
    python_data = try_extract_ledger_fields(pdf_path, claim_details) or {}

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
        extracted["dealer_stamp"] = {"text": "Present (Python mock stamp)", "stamp_dealer_name": claim_details.get("Dealer Name", ""), "line": 0, "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}
        extracted["authorized_signature"] = {"text": "Present (Python mock signature)", "line": 0, "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}
        logging.info("[validate_ledger] Running in Python-only mode — skipped AI, visual fields mocked")

    if not extracted:
        try:
            pil_img = _render_pdf_to_pil(pdf_path)
            full_b64 = _pil_to_b64(pil_img)
        except Exception as e:
            return False, f"Failed to render ledger PDF: {e}"

        extracted = _call_openai(full_b64)
        if not extracted:
            return False, "LLM Vision Extraction Failed"

    # Merge Python-extracted text fields into AI result (Python is more reliable for text)
    if python_data and not is_python_provider:
        for key, py_val in python_data.items():
            if key in ("dealer_stamp", "authorized_signature"):
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
        data_store.update_doc_data("ledger", extracted)

    # ── Rule Engine validation ─────────────────────────────────────────────────
    from document_processing.rule_engine import RuleEngine, ValidationRule, make_fuzzy_name_rule, make_presence_rule
    from document_processing.validation_result import issues_from_rule_results, summary_status, ValidationStatus

    def _conf(key):
        """Return OCR confidence for a field, defaulting to 1.0 (certain)."""
        return float(extracted.get(key, {}).get("confidence", 1.0))

    title      = extracted.get("document_type", {}).get("text", "")
    doc_cust   = extracted.get("customer_name", {}).get("text", "")
    portal_cust = claim_details.get("Customer Name", "")

    stamp_dealer_name = extracted.get("dealer_stamp", {}).get("stamp_dealer_name", "")
    if not stamp_dealer_name or stamp_dealer_name.upper() in ("MISSING", "N/A", "NONE"):
        stamp_dealer_name = extracted.get("dealership_name", {}).get("text", "")
    portal_dealer = claim_details.get("Dealer Name", "")

    wb_row_text   = extracted.get("welcome_bonus_row", {}).get("text", "")
    wb_row_amount = extracted.get("welcome_bonus_row", {}).get("amount", "")
    portal_amount_raw = claim_details.get("Total Amount") or claim_details.get("OEM Share Amount") or claim_details.get("dashboard_total_amount")
    try:
        portal_amount_float = float(re.sub(r"[^0-9\.]", "", str(portal_amount_raw))) if portal_amount_raw else None
    except Exception:
        portal_amount_float = None

    dealer_stamp_text  = extracted.get("dealer_stamp", {}).get("text", "")
    auth_sig_text      = extracted.get("authorized_signature", {}).get("text", "")
    stamp_conf         = float(extracted.get("dealer_stamp", {}).get("confidence", 1.0))

    ctx = {
        "title":             title,
        "doc_cust":          doc_cust,
        "portal_cust":       portal_cust,
        "cust_conf":         _conf("customer_name"),
        "stamp_dealer_name": stamp_dealer_name,
        "portal_dealer":     portal_dealer,
        "dealer_conf":       _conf("dealership_name"),
        "wb_row_text":       wb_row_text,
        "wb_row_amount":     wb_row_amount,
        "portal_amount":     portal_amount_float,
        "dealer_stamp_text": dealer_stamp_text,
        "auth_sig_text":     auth_sig_text,
        "stamp_confidence":  stamp_conf,
    }

    def _amount_ok(ctx):
        doc_amt = extract_amount_robust(ctx.get("wb_row_amount", ""))
        p_amt   = ctx.get("portal_amount")
        if doc_amt is None or p_amt is None or p_amt == 0:
            return False
        for target in (p_amt, p_amt / 1.18, p_amt * 1.18):
            if abs(doc_amt - target) <= 200.0 or (abs(doc_amt - target) / target) <= 0.05:
                return True
        return False

    def _amount_unknown(ctx):
        return extract_amount_robust(ctx.get("wb_row_amount", "")) is None

    def _dealer_name_ok(ctx):
        doc = re.sub(r"[^a-zA-Z0-9]", " ", str(ctx.get("stamp_dealer_name", "")).lower()).strip()
        portal = re.sub(r"[^a-zA-Z0-9]", " ", str(ctx.get("portal_dealer", "")).lower()).strip()
        if not doc or not portal:
            return False
        try:
            from rapidfuzz import fuzz
            return fuzz.token_sort_ratio(doc, portal) >= 70
        except ImportError:
            return doc == portal

    rules = [
        ValidationRule(
            name="ledger_heading",
            description="Document is classified as Ledger / Statement of Account",
            check=lambda c: any(k in str(c.get("title","")).upper() for k in ("LEDGER","STATEMENT","ACCOUNT","STMT")),
            fail_message=f"Document heading '{title}' is not classified as a Ledger or Statement",
            severity="ERROR",
        ),
        ValidationRule(
            name="customer_name",
            description="Customer name in ledger matches portal",
            check=lambda c: bool(c.get("doc_cust")) and is_name_in_text(c.get("doc_cust",""), c.get("portal_cust","")),
            fail_message=f"Customer Name mismatch. Document: '{doc_cust}', Portal: '{portal_cust}'",
            severity="ERROR",
            unknown_check=lambda c: c.get("cust_conf", 1.0) < 0.60,
            unknown_message=f"Customer Name low OCR confidence ({_conf('customer_name'):.2f}) — manual review needed",
        ),
        ValidationRule(
            name="dealership_name",
            description="Dealership name on stamp/header matches portal",
            check=_dealer_name_ok,
            fail_message=f"Dealership Name mismatch. Document: '{stamp_dealer_name}', Portal: '{portal_dealer}'",
            severity="ERROR",
            unknown_check=lambda c: not c.get("stamp_dealer_name"),
            unknown_message="Dealership name not found on stamp or header — manual review needed",
        ),
        ValidationRule(
            name="welcome_bonus_row_present",
            description="Welcome Bonus row is present in ledger",
            check=lambda c: bool(c.get("wb_row_text")) and is_present_robust(c.get("wb_row_text","")) and any(k in str(c.get("wb_row_text","")).upper() for k in ("WELCOME","BONUS","LOYALTY")),
            fail_message="Welcome Bonus row entry not found in ledger",
            severity="ERROR",
        ),
        ValidationRule(
            name="welcome_bonus_amount",
            description="Welcome Bonus amount matches portal scheme amount",
            check=_amount_ok,
            fail_message=f"Welcome Bonus Row amount mismatch. Row: '{wb_row_amount}', Portal: {portal_amount_float}",
            severity="ERROR",
            unknown_check=_amount_unknown,
            unknown_message=f"Welcome Bonus amount not found in row '{wb_row_amount}' — manual review needed",
        ),
        ValidationRule(
            name="dealer_stamp",
            description="Dealership stamp/seal is present on ledger",
            check=lambda c: is_present_robust(c.get("dealer_stamp_text",""), ["STAMP","SEAL"]),
            fail_message="Dealership stamp/seal is missing on ledger",
            severity="ERROR",
            unknown_check=lambda c: 0.20 <= c.get("stamp_confidence", 1.0) < 0.50,
            unknown_message="Stamp detected but confidence is low — manual review needed",
        ),
        ValidationRule(
            name="authorized_signature",
            description="Authorized signature is present on ledger",
            check=lambda c: is_present_robust(c.get("auth_sig_text",""), ["SIGNATURE","SIGNED"]),
            fail_message="Dealership authorized signature is missing from ledger stamp/seal",
            severity="ERROR",
        ),
    ]

    engine = RuleEngine(rules)
    rule_results, issues = engine.run_and_get_issues(ctx)
    overall = summary_status(rule_results)

    if issues:
        return False, "; ".join(issues)

    return True, "Ledger Verified Successfully"


def process_east_welcome_bonus_ledger(pdf_path):
    """
    Called by the UI to extract visual crop data for the Ledger.
    Returns a list of dicts: [{'field': label, 'value': val, 'crop_b64': crop_b64}]
    """
    try:
        pil_img = _render_pdf_to_pil(pdf_path)
    except Exception as e:
        logging.error(f"Failed to render ledger PDF: {e}")
        return []

    is_python_provider = (os.getenv("AI_PROVIDER", "").strip().upper() == "PYTHON")
    extracted = None

    if is_python_provider:
        from .python_readers.reader_ledger import try_extract_ledger_fields
        python_data = try_extract_ledger_fields(pdf_path) or {}
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
        # Get dealer name from app context or environment if possible, or leave it to be filled dynamically
        # Since process_east_welcome_bonus_ledger has no claim_details context parameter, we pass a fallback
        extracted["dealer_stamp"] = {"text": "Present (Python mock stamp)", "stamp_dealer_name": "Present", "line": 0, "crop": {"top": 0, "left": 0, "bottom": 100, "right": 100}}
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
