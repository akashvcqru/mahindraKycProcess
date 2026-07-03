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
    # Fallbacks in case execution environment differs
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


# ── System Prompt for Certificate of Deposit / Scrappage Certificate ─────────
OEM_PROMPT = """You are an advanced document analysis AI. Your task is to read this Certificate of Deposit (COD) / Scrappage Certificate document line by line from top to bottom.

Extract ONLY the following 2 fields:
1. Certificate of Deposit Number (Certificate Deposit Number / Scrapped Vehicle Chassis Number) — Look for the certificate number, registration number, or scrapped/old vehicle chassis number in the document.
2. New Vehicle Chassis Number — Look for the new vehicle chassis number, or general chassis number mentioned in the document.

For each field also return:
- The exact text found
- Which line number (approx) it appears on
- A crop bounding box as percentage of image width/height: {top%, left%, bottom%, right%}
  (IMPORTANT: Ensure coordinates accurately reflect the spatial location in the image. Do NOT hallucinate coordinates.)

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
                    {"type": "text", "text": OEM_PROMPT},
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
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as exc:
            if attempt == max_retries - 1:
                logging.error(f"OpenAI OEM call failed: {exc}")
                return None
            time.sleep(2)
    return None


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

    full_b64 = _pil_to_b64(pil_img)
    extracted = _call_openai(full_b64)

    if not extracted:
        return False, "LLM Extraction Failed"

    if data_store:
        data_store.update_doc_data("oem_document", extracted)

    issues = []

    # 1. Certificate of Deposit number must match old vehicle Chassis No
    cert_no = extracted.get("certificate_deposit_no", {}).get("text", "").strip()
    old_chassis_web = old_vehicle_details.get("Chassis No", "").strip()

    if not cert_no:
        issues.append("Certificate of Deposit No not found in document")
    elif old_chassis_web:
        status_cert, score_cert = compare_values_robust(cert_no, old_chassis_web)
        if not status_cert.startswith("MATCH"):
            issues.append(
                f"Certificate No mismatch (Document Certificate No: '{cert_no}' does not match old vehicle chassis: '{old_chassis_web}')"
            )

    # 2. Chassis Number in the document (new vehicle chassis) last 8 characters must match dashboard claim details
    doc_chassis = extracted.get("chassis_no", {}).get("text", "").strip()
    new_chassis_web = claim_details.get("Chassis No", "").strip()

    if not doc_chassis:
        # Check raw text backup just in case LLM missed the structured new chassis key but it exists in the document
        try:
            # Re-read page text via fitz
            doc = fitz.open(pdf_path)
            text_str = doc[0].get_text()
        except Exception:
            text_str = ""
        matched_new = find_chassis_in_text(text_str, new_chassis_web, match_last_8=True)
        if not matched_new:
            issues.append("New Chassis number not found in OEM Document")
    elif new_chassis_web:
        matched_new = find_chassis_in_text(doc_chassis, new_chassis_web, match_last_8=True)
        if not matched_new:
            issues.append(
                f"New Chassis mismatch (Document Chassis: '{doc_chassis}' does not match last 8 digits of dashboard: '{new_chassis_web}')"
            )

    if issues:
        return False, "; ".join(issues)
    return True, "OEM Document Validated"


# ── PUBLIC: process_oem_visual (called by app_ui.py) ───────────────────────
def process_oem_visual(pdf_path):
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
    extracted = _call_openai(full_b64)

    if not extracted:
        return _generate_mock_response(pil_img)

    return _pair_crops(pil_img, extracted)
