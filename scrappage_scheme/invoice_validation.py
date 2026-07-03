import base64
import io
import json
import logging
import os
import time

import fitz
import requests
from PIL import Image


# ── System Prompt (derived from invoice_analyzer.html) ─────────────────────
INVOICE_PROMPT = """You are an advanced document analysis AI. Your task is to read this tax invoice image line by line from top to bottom.

Extract ONLY the following 7 fields in this exact order:
1. Dealership Name — the company/dealer name from the header at the very top of the document (name only, no address)
2. Document Type — the label printed on the document, e.g. "Tax Invoice", "GST Invoice", "Retail Invoice"
3. GST Invoice Number and Date — the invoice number AND the invoice date together
4. Customer Name — the buyer/customer name exactly as printed on the document
5. OEM Loyalty / Scrappage Bonus Discount — Prioritize looking for a specific note text on the page such as "Note : Scrappage Bonus Amount is Rs.XXXX" or "Note : Loyalty Bonus Amount is Rs.XXXX" (which is often printed at the bottom or middle). If such a note exists, extract its full text and the rupee amount (e.g. 45000.00). If no such note exists, look in the table line items for "OEM LOYALTY DISCOUNT", "SCRAPPAGE BONUS", "OEM Discount", or similar.
6. Customer Signature — State: "Present" or "Missing". If present, briefly note whether it appears to match the customer name line.
7. Dealership Stamp and Seal — Describe what is printed (dealer name, designation, reverse charge note). State "Present" or "Missing".

For each field also return:
- The exact text found
- Which line number (approx) it appears on
- A crop bounding box as percentage of image width/height: {top%, left%, bottom%, right%}
  (IMPORTANT: Ensure coordinates accurately reflect the spatial location. E.g. if the stamp is at the very bottom, top% should be > 80. Do NOT hallucinate coordinates.)

Respond ONLY in this JSON format (no markdown, no extra text):
{
  "dealership_name":   {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "document_type":     {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "invoice_no_date":   {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "customer_name":     {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "oem_discount":      {"text": "...", "amount": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
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
                    {"type": "text", "text": INVOICE_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{full_b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 1800,
        "temperature": 0.0,
    }

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logging.warning(f"Invoice vision retry {attempt + 1}/{max_retries}…")
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
                logging.error(f"OpenAI invoice call failed after {max_retries} attempts: {exc}")
                return None
            if "429" in str(exc) or "Too Many Requests" in str(exc):
                time.sleep(5 * (2 ** attempt))
            else:
                time.sleep(2)
    return None


# ── Field mapping: JSON key → human-readable label ─────────────────────────
FIELD_MAPPING = {
    "dealership_name":    "Dealership Name",
    "document_type":      "Document Type",
    "invoice_no_date":    "GST Invoice Number & Date",
    "customer_name":      "Customer Name",
    "oem_discount":       "OEM / Scrappage Bonus Discount",
    "customer_signature": "Customer Signature",
    "dealer_stamp":       "Dealership Stamp & Seal",
}

FIELD_ORDER = [
    "dealership_name",
    "document_type",
    "invoice_no_date",
    "customer_name",
    "oem_discount",
    "customer_signature",
    "dealer_stamp",
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

        # Value: for oem_discount prefer amount
        if key == "oem_discount":
            val = data.get("amount", data.get("text", ""))
            val = f"{data.get('text','').strip()} — ₹{val}" if val else data.get("text", "")
        else:
            val = data.get("text", "")

        crop_info = data.get("crop", {})
        top_pct    = crop_info.get("top",    0)  / 100.0
        left_pct   = crop_info.get("left",   0)  / 100.0
        bottom_pct = crop_info.get("bottom", 100) / 100.0
        right_pct  = crop_info.get("right",  100) / 100.0

        PAD_X, PAD_Y = 50, 50
        x1 = max(0, int(left_pct   * width)  - PAD_X)
        y1 = max(0, int(top_pct    * height) - PAD_Y)
        x2 = min(width,  int(right_pct  * width)  + PAD_X)
        y2 = min(height, int(bottom_pct * height) + PAD_Y)

        # Guard against degenerate boxes
        if x2 <= x1: x2 = min(width,  x1 + 10)
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


def _generate_mock_response(pil_img):
    """Return a placeholder result when the API is unavailable."""
    mock = {
        "dealership_name":    {"text": "API Error", "line": 1,  "crop": {"top": 0,  "left": 0, "bottom": 10, "right": 100}},
        "document_type":      {"text": "API Error", "line": 2,  "crop": {"top": 5,  "left": 0, "bottom": 15, "right": 100}},
        "invoice_no_date":    {"text": "API Error", "line": 3,  "crop": {"top": 10, "left": 0, "bottom": 20, "right": 100}},
        "customer_name":      {"text": "API Error", "line": 10, "crop": {"top": 20, "left": 0, "bottom": 30, "right": 100}},
        "oem_discount":       {"text": "API Error", "amount": "–", "line": 20, "crop": {"top": 50, "left": 0, "bottom": 70, "right": 100}},
        "customer_signature": {"text": "API Error", "line": 30, "crop": {"top": 75, "left": 0, "bottom": 90, "right": 100}},
        "dealer_stamp":       {"text": "API Error", "line": 35, "crop": {"top": 85, "left": 0, "bottom": 100, "right": 100}},
    }
    return _pair_crops(pil_img, mock)


# ── PUBLIC: validate_invoice (called by processor.py for hold/approved) ─────
def validate_invoice(pdf_path, claim_details, data_store):
    """
    Validates a Scrappage Invoice document.
    Returns (success: bool, message: str).
    """
    logging.info(f"Validating Scrappage Invoice: {pdf_path}")

    if not os.path.exists(pdf_path):
        logging.error("Invoice PDF not found.")
        return False, "Invoice PDF not found"

    try:
        pil_img = _render_pdf_to_pil(pdf_path)
    except Exception as exc:
        logging.error(f"Failed to render invoice {pdf_path}: {exc}")
        return False, f"Failed to load image: {exc}"

    full_b64 = _pil_to_b64(pil_img)
    extracted = _call_openai(full_b64)

    if not extracted:
        return False, "LLM Extraction Failed"

    # Persist extracted data for later reference
    if data_store:
        data_store.update_doc_data("invoice", extracted)

    # ── Validation rules ────────────────────────────────────────────────────
    issues = []

    # 1. Dealer stamp / seal must be present
    stamp_text = extracted.get("dealer_stamp", {}).get("text", "").lower()
    if "missing" in stamp_text or not stamp_text.strip():
        issues.append("Dealer stamp/seal is MISSING on the invoice")

    # 2. Customer signature must be present
    sig_text = extracted.get("customer_signature", {}).get("text", "").lower()
    if "missing" in sig_text or not sig_text.strip():
        issues.append("Customer signature is MISSING on the invoice")

    # 3. OEM / Scrappage discount must be present
    oem_text = extracted.get("oem_discount", {}).get("text", "").strip()
    oem_amt  = extracted.get("oem_discount", {}).get("amount", "").strip()
    if not oem_text or not oem_amt or oem_amt in ("-", "0", ""):
        issues.append("OEM/Scrappage Bonus discount line not found on invoice")

    # 4. Customer name must be present
    cust_text = extracted.get("customer_name", {}).get("text", "").strip()
    if not cust_text:
        issues.append("Customer name not found on invoice")
    else:
        # Cross-check name against claim details (fuzzy match)
        claim_name = claim_details.get("Customer Name", "").strip().lower()
        if claim_name and claim_name not in cust_text.lower():
            issues.append(
                f"Invoice customer name '{cust_text}' does not match claim customer '{claim_name}'"
            )

    if issues:
        return False, "; ".join(issues)
    return True, "Invoice Validated"


# ── PUBLIC: process_invoice_visual (called by app_ui.py for crop images) ───
def process_invoice_visual(pdf_path):
    """
    Extracts invoice fields visually and generates cropped images for the UI.
    Returns a list of dicts: [{field, value, crop_b64}, …]
    """
    logging.info(f"[UI] Processing Invoice Visual: {pdf_path}")

    if not os.path.exists(pdf_path):
        logging.error("Invoice PDF not found.")
        return []

    try:
        pil_img = _render_pdf_to_pil(pdf_path)
    except Exception as exc:
        logging.error(f"Failed to render invoice {pdf_path}: {exc}")
        return []

    full_b64 = _pil_to_b64(pil_img)
    extracted = _call_openai(full_b64)

    if not extracted:
        return _generate_mock_response(pil_img)

    return _pair_crops(pil_img, extracted)
