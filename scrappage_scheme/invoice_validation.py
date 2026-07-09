import base64
import io
import json
import logging
import os
import time
import re

import fitz
import requests
from PIL import Image


# ── System Prompt ────────────────────────────────────────────────────────────
INVOICE_PROMPT = """You are an expert document analysis AI. Carefully analyze this TAX INVOICE image.

Your task is to locate and extract 9 specific fields. For EVERY field:
- Identify the actual CONTENT (not the label/heading text itself)
- Return precise bounding box coordinates (as % of image dimensions) that frame the CONTENT AREA with generous padding
- The crop must show the actual value/image, NOT just the row label

=== CRITICAL CROPPING RULES ===
- NEVER return coordinates that only capture a text label like "Customer Signature :" or "Dealer Stamp :" — those are just labels
- For SIGNATURES: The customer may have signed ANYWHERE on the document (near IRN Number row, middle of page, or bottom). Search the ENTIRE document for any handwritten ink/cursive writing. Crop the region where the ink appears with at least 8% vertical height.
- For STAMPS: The dealer stamp/seal is a CIRCULAR or OVAL rubber stamp image with printed text inside. It is usually in the bottom-right or middle-right area. Crop the actual circle/oval stamp graphic with at least 8% vertical height.
- For STAMP SIGNATURE: Look for a handwritten signature that appears INSIDE or DIRECTLY ABOVE/BELOW the circular stamp. This is the authorised signatory's signature. It may overlap with the stamp. Crop both together.
- For INVOICE NUMBER: Crop the full row containing the GST Invoice Number AND Invoice Date together. Minimum 3% vertical height.
- All crop values must be realistic percentages of the actual image. Do NOT hallucinate. If genuinely not found, use "Missing" for text and return approximate area where it should be.

=== FIELDS TO EXTRACT ===

1. dealership_name
   - The dealership/company name from the HEADER at the very top of the document
   - Name only, no address

2. document_type
   - The document classification label printed prominently e.g. "TAX INVOICE", "GST INVOICE", "RETAIL INVOICE"

3. invoice_no_date
   - The GST Invoice Number AND the Invoice Date together
   - Example: "INV27M000018, Date: 18/06/2026"

4. customer_name
   - The buyer/customer full name exactly as printed

5. oem_discount
   - Look for NOTE text like "Scrappage Bonus Amount is Rs.XXXX" or "Loyalty Bonus Amount is Rs.XXXX" printed anywhere on the page
   - If found: return full note text and extract the rupee amount separately
   - If not in a note: look in table line items for "OEM Discount", "OEM LOYALTY DISCOUNT", "SCRAPPAGE BONUS", etc.

6. customer_signature
   - Search the ENTIRE page for any handwritten cursive ink — this is the customer signature
   - It is often found near the "IRN Number" row or at the bottom "Customer Signature" section
   - State "Present" or "Missing" in text
   - Crop the actual handwritten ink area (not the label) with generous padding

7. dealer_stamp
   - Find the actual CIRCULAR/OVAL rubber stamp graphic with the dealer name printed inside
   - It is usually in the bottom-right area of the invoice
   - State "Present" or "Missing" in text
   - Crop the actual stamp circle/oval image

8. stamp_signature
   - Look for a handwritten signature that is ON, INSIDE, or directly ABOVE/BELOW the dealer stamp
   - This is the "Authorised Signatory" signature
   - State "Present" or "Missing" in text
   - Crop the area including both the stamp and the signature overlapping/adjacent to it
   - If no such signature exists on/near stamp, state "Missing"

9. stamp_digitally_signed
   - Look anywhere near the dealer stamp or authorised signatory area for text like:
     "Digitally Signed", "e-Signed", "Digital Signature", "This document is digitally signed"
   - Return "Yes" if found, "No" if not found

=== RESPONSE FORMAT ===
Respond ONLY with valid JSON (no markdown fences, no extra text):
{
  "dealership_name":        {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "document_type":          {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "invoice_no_date":        {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "customer_name":          {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "oem_discount":           {"text": "...", "amount": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "customer_signature":     {"text": "Present|Missing", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "dealer_stamp":           {"text": "Present|Missing", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "stamp_signature":        {"text": "Present|Missing", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "stamp_digitally_signed": {"text": "Yes|No", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}}
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
        "model": "gpt-5.5",
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


# ── Minimum crop height (% of image) per field ──────────────────────────────
# Ensures crops are large enough to actually show content, not just label rows
_MIN_CROP_HEIGHT_PCT = {
    "customer_signature":     8,   # Handwritten signature needs height to be visible
    "dealer_stamp":           8,   # Circular stamp needs height
    "stamp_signature":        10,  # Stamp + signature overlap — give extra room
    "invoice_no_date":        3,   # At least one full table row
    "oem_discount":           3,
    "dealership_name":        3,
    "document_type":          3,
    "customer_name":          2,
    "stamp_digitally_signed": 2,
}

# ── Field mapping: JSON key → human-readable label ─────────────────────────
FIELD_MAPPING = {
    "dealership_name":        "Dealership Name",
    "document_type":          "Document Type",
    "invoice_no_date":        "GST Invoice Number & Date",
    "customer_name":          "Customer Name",
    "oem_discount":           "OEM / Scrappage Bonus Discount",
    "customer_signature":     "Customer Signature",
    "dealer_stamp":           "Dealership Stamp & Seal",
    "stamp_signature":        "Authorised Signatory (on Stamp)",
    "stamp_digitally_signed": "Stamp: Digitally Signed",
}

FIELD_ORDER = [
    "dealership_name",
    "document_type",
    "invoice_no_date",
    "customer_name",
    "oem_discount",
    "customer_signature",
    "dealer_stamp",
    "stamp_signature",
    "stamp_digitally_signed",
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

        crop_info  = data.get("crop", {})
        top_pct    = crop_info.get("top",    0)   / 100.0
        left_pct   = crop_info.get("left",   0)   / 100.0
        bottom_pct = crop_info.get("bottom", 100) / 100.0
        right_pct  = crop_info.get("right",  100) / 100.0

        # ── Enforce minimum crop height so label-only crops are expanded ──────
        min_h_pct = _MIN_CROP_HEIGHT_PCT.get(key, 2) / 100.0
        if (bottom_pct - top_pct) < min_h_pct:
            centre     = (top_pct + bottom_pct) / 2.0
            half       = min_h_pct / 2.0
            top_pct    = max(0.0, centre - half)
            bottom_pct = min(1.0, centre + half)

        PAD_X, PAD_Y = 40, 30
        x1 = max(0,      int(left_pct   * width)  - PAD_X)
        y1 = max(0,      int(top_pct    * height) - PAD_Y)
        x2 = min(width,  int(right_pct  * width)  + PAD_X)
        y2 = min(height, int(bottom_pct * height) + PAD_Y)

        # Guard against degenerate boxes
        if x2 <= x1: x2 = min(width,  x1 + 20)
        if y2 <= y1: y2 = min(height, y1 + 20)

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
        "dealership_name":        {"text": "API Error", "line": 1,  "crop": {"top": 0,  "left": 0,  "bottom": 8,  "right": 100}},
        "document_type":          {"text": "API Error", "line": 2,  "crop": {"top": 8,  "left": 0,  "bottom": 15, "right": 100}},
        "invoice_no_date":        {"text": "API Error", "line": 3,  "crop": {"top": 15, "left": 0,  "bottom": 22, "right": 100}},
        "customer_name":          {"text": "API Error", "line": 10, "crop": {"top": 22, "left": 0,  "bottom": 32, "right": 100}},
        "oem_discount":           {"text": "API Error", "amount": "–", "line": 20, "crop": {"top": 60, "left": 0, "bottom": 70, "right": 100}},
        "customer_signature":     {"text": "API Error", "line": 30, "crop": {"top": 70, "left": 0,  "bottom": 82, "right": 100}},
        "dealer_stamp":           {"text": "API Error", "line": 35, "crop": {"top": 82, "left": 50, "bottom": 95, "right": 100}},
        "stamp_signature":        {"text": "API Error", "line": 36, "crop": {"top": 80, "left": 50, "bottom": 95, "right": 100}},
        "stamp_digitally_signed": {"text": "No",        "line": 36, "crop": {"top": 80, "left": 50, "bottom": 95, "right": 100}},
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

    # Collect stamp / stamp-signature status first
    stamp_text        = extracted.get("dealer_stamp",        {}).get("text", "").lower()
    stamp_sig_text    = extracted.get("stamp_signature",     {}).get("text", "").lower()
    dig_text          = extracted.get("stamp_digitally_signed", {}).get("text", "No").strip().lower()

    stamp_missing     = "missing" in stamp_text     or not stamp_text.strip()
    stamp_sig_missing = "missing" in stamp_sig_text or not stamp_sig_text.strip()
    is_digitally_signed = (dig_text == "yes")

    # Rules 1 & 3 — Dealer stamp + Signature on stamp
    # HOLD only when BOTH are missing AND "This document is digitally signed" is NOT present.
    # If only one is missing, or both are present → no issue.
    if stamp_missing and stamp_sig_missing:
        if is_digitally_signed:
            logging.info(
                "Dealer stamp & stamp signature both absent but "
                "'This document is digitally signed' found — PASS"
            )
        else:
            issues.append(
                "Dealer stamp/seal and authorised signature are both MISSING "
                "and no 'This document is digitally signed' text found"
            )

    # 2. Customer signature must be present (anywhere on the document)
    sig_text = extracted.get("customer_signature", {}).get("text", "").lower()
    if "missing" in sig_text or not sig_text.strip():
        issues.append("Customer signature is MISSING on the invoice")


    # 4. OEM / Scrappage discount must be present
    oem_text = extracted.get("oem_discount", {}).get("text",   "").strip()
    oem_amt  = extracted.get("oem_discount", {}).get("amount", "").strip()
    if not oem_text or not oem_amt or oem_amt in ("-", "0", ""):
        issues.append("OEM/Scrappage Bonus discount line not found on invoice")

    # 5. Customer name must be present and match claim
    cust_text = extracted.get("customer_name", {}).get("text", "").strip()
    if not cust_text:
        issues.append("Customer name not found on invoice")
    else:
        claim_name = claim_details.get("Customer Name", "").strip()
        c1 = re.sub(r"[^A-Z0-9\s]", "", cust_text.upper()).strip()
        c2 = re.sub(r"[^A-Z0-9\s]", "", claim_name.upper()).strip()

        c2_words   = [w for w in c2.split() if len(w) >= 3]
        word_match = bool(c2_words) and all(w in c1 for w in c2_words)

        import difflib
        ratio = difflib.SequenceMatcher(None, c1, c2).ratio()

        if c2 and not (c2 in c1 or c1 in c2 or word_match or ratio >= 0.80):
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
