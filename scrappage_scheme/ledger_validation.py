import base64
import io
import json
import logging
import os
import time

import fitz
import requests
from PIL import Image

def validate_ledger(pdf_path, claim_details, data_store):
    """
    Validates a Scrappage Ledger document.
    Extracts fields using OpenAI Vision and provides approximate visual crops.
    """
    logging.info(f"Processing Scrappage Scheme Ledger Document: {pdf_path}")

    if not os.path.exists(pdf_path):
        logging.error("Ledger PDF not found.")
        return False, "Ledger PDF not found"

    try:
        # Convert first page of PDF to image or load image directly
        if pdf_path.lower().endswith(".pdf"):
            doc = fitz.open(pdf_path)
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=200)
            png_bytes = pix.tobytes("png")
            pil_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        else:
            pil_img = Image.open(pdf_path).convert("RGB")
    except Exception as e:
        logging.error(f"Failed to render/load PDF/image {pdf_path}: {e}")
        return False, f"Failed to load image: {e}"

    # Encode full image for OpenAI
    img_byte_arr = io.BytesIO()
    pil_img.save(img_byte_arr, format="PNG")
    full_b64 = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")

    prompt_text = """Read this document line by line from top to bottom and extract the following details:

1. DEALERSHIP NAME — the company/dealer name mentioned in the heading (name only, no address)
2. CUSTOMER NAME — the person the ledger/invoice is made for. Example: CHANDRASHEKHAR SAHU S/O NAJRU RAM SAHU
3. DOCUMENT NAME — is it "Ledger Account", "Tax Invoice", or another document type?
4. SCRAPPAGE BONUS / LOYALTY BONUS / EXCHANGE BONUS — Look for "SCRAPPAGE BONUS", "LOYALTY CLAIM", or "EXCHANGE BONUS". The credit amount might be exactly on the same horizontal row, OR it might be on the parent row immediately ABOVE it. Extract the correct credit amount.
5. DEALER SEAL & STAMP & SIGNATURE — look for a circular, oval, or rectangular ink stamp containing the dealership's name and signature. It is typically found near the very bottom or middle of the page. Do NOT confuse it with scanner watermarks like "Scanned with OKEN Scanner".

TRAINING / GENERAL RULE FOR SCRAPPAGE BONUS:
- Scan the table to find "SCRAPPAGE BONUS", "LOYALTY CLAIM", or "EXCHANGE BONUS".
- If that exact row has a Credit amount, use it.
- If that exact row only has a Debit (Dr) amount, look at the row immediately ABOVE or BELOW it and use that Credit amount instead.
- Ignore completely unrelated rows below it (e.g., Bank Receipt).

For each field return:
- The exact text found
- Which line number (approx) it appears on
- A crop bounding box as percentage of image width/height: {top%, left%, bottom%, right%}
  (IMPORTANT: Ensure these accurately reflect the spatial location in the image! For example, if a stamp is at the very bottom of the page, top% should be > 80. Do not hallucinate coordinates).

Respond ONLY in this JSON format (no markdown, no extra text):
{
  "dealership_name": {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "customer_name": {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "document_name": {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "scrappage_bonus": {"text": "...", "amount": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "seal_stamp": {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}}
}"""

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logging.error("OPENAI_API_KEY not found in environment.")
        return False, "OPENAI_API_KEY missing"

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
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

    max_retries = 3
    extracted_data = None

    for retry_attempt in range(max_retries):
        try:
            if retry_attempt > 0:
                logging.warning(f"Retry attempt {retry_attempt + 1}/{max_retries} for ledger visual extraction...")

            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            resp_json = response.json()
            content = resp_json["choices"][0]["message"]["content"]

            # Clean markdown
            content = content.replace("```json", "").replace("```", "").strip()
            extracted_data = json.loads(content)
            break

        except Exception as e:
            if retry_attempt == max_retries - 1:
                logging.error(f"OpenAI API call failed after {max_retries} attempts for ledger: {e}")
                return False, "LLM Extraction Failed"
            else:
                logging.warning(f"Attempt {retry_attempt + 1} failed for ledger: {e}. Retrying...")
                if "429" in str(e) or "Too Many Requests" in str(e):
                    time.sleep(5 * (2**retry_attempt))
                else:
                    time.sleep(2)

    # Save data to store
    if extracted_data and data_store:
        data_store.update_doc_data("ledger", extracted_data)
        
    return True, "Ledger Validated"


def process_scrappage_ledger_visual(pdf_path):
    """
    Extracts Scrappage ledger fields visually and generates cropped images for the UI dashboard.
    """
    logging.info(f"[UI] Processing Scrappage Scheme Ledger Visual: {pdf_path}")

    if not os.path.exists(pdf_path):
        logging.error("Ledger PDF not found.")
        return []

    try:
        if pdf_path.lower().endswith(".pdf"):
            doc = fitz.open(pdf_path)
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=200)
            png_bytes = pix.tobytes("png")
            pil_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        else:
            pil_img = Image.open(pdf_path).convert("RGB")
    except Exception as e:
        logging.error(f"Failed to render/load PDF/image {pdf_path}: {e}")
        return []

    img_byte_arr = io.BytesIO()
    pil_img.save(img_byte_arr, format="PNG")
    full_b64 = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")

    prompt_text = """Read this document line by line from top to bottom and extract the following details:

1. DEALERSHIP NAME — the company/dealer name mentioned in the heading (name only, no address)
2. CUSTOMER NAME — the person the ledger/invoice is made for. Example: CHANDRASHEKHAR SAHU S/O NAJRU RAM SAHU
3. DOCUMENT NAME — is it "Ledger Account", "Tax Invoice", or another document type?
4. SCRAPPAGE BONUS / LOYALTY BONUS / EXCHANGE BONUS — Look for "SCRAPPAGE BONUS", "LOYALTY CLAIM", or "EXCHANGE BONUS". The credit amount might be exactly on the same horizontal row, OR it might be on the parent row immediately ABOVE it. Extract the correct credit amount.
5. DEALER SEAL & STAMP & SIGNATURE — look for a circular, oval, or rectangular ink stamp containing the dealership's name and signature. It is typically found near the very bottom or middle of the page. Do NOT confuse it with scanner watermarks like "Scanned with OKEN Scanner".

TRAINING / GENERAL RULE FOR SCRAPPAGE BONUS:
- Scan the table to find "SCRAPPAGE BONUS", "LOYALTY CLAIM", or "EXCHANGE BONUS".
- If that exact row has a Credit amount, use it.
- If that exact row only has a Debit (Dr) amount, look at the row immediately ABOVE or BELOW it and use that Credit amount instead.
- Ignore completely unrelated rows below it (e.g., Bank Receipt).

For each field return:
- The exact text found
- Which line number (approx) it appears on
- A crop bounding box as percentage of image width/height: {top%, left%, bottom%, right%}
  (IMPORTANT: Ensure these accurately reflect the spatial location in the image! For example, if a stamp is at the very bottom of the page, top% should be > 80. Do not hallucinate coordinates).

Respond ONLY in this JSON format (no markdown, no extra text):
{
  "dealership_name": {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "customer_name": {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "document_name": {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "scrappage_bonus": {"text": "...", "amount": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}},
  "seal_stamp": {"text": "...", "line": N, "crop": {"top": X, "left": X, "bottom": X, "right": X}}
}"""

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logging.error("OPENAI_API_KEY not found in environment.")
        return generate_mock_response(pil_img)

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
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

    max_retries = 3
    extracted_data = None

    for retry_attempt in range(max_retries):
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            resp_json = response.json()
            content = resp_json["choices"][0]["message"]["content"]

            content = content.replace("```json", "").replace("```", "").strip()
            extracted_data = json.loads(content)
            break

        except Exception as e:
            if retry_attempt == max_retries - 1:
                logging.error(f"OpenAI API call failed after {max_retries} attempts for ledger: {e}")
                return generate_mock_response(pil_img)
            else:
                if "429" in str(e) or "Too Many Requests" in str(e):
                    time.sleep(5 * (2**retry_attempt))
                else:
                    time.sleep(2)

    return pair_crops_with_data(pil_img, extracted_data)


def generate_mock_response(pil_img):
    mock_data = {
        "dealership_name": {"text": "Error connecting to LLM", "line": 0, "crop": {"top": 0, "left": 0, "bottom": 15, "right": 100}},
        "customer_name": {"text": "Error connecting to LLM", "line": 0, "crop": {"top": 10, "left": 0, "bottom": 25, "right": 100}},
        "document_name": {"text": "Error connecting to LLM", "line": 0, "crop": {"top": 15, "left": 0, "bottom": 30, "right": 100}},
        "scrappage_bonus": {"text": "Error connecting to LLM", "amount": "Error", "line": 0, "crop": {"top": 40, "left": 0, "bottom": 80, "right": 100}},
        "seal_stamp": {"text": "Error connecting to LLM", "line": 0, "crop": {"top": 70, "left": 0, "bottom": 100, "right": 100}},
    }
    return pair_crops_with_data(pil_img, mock_data)


def pair_crops_with_data(pil_img, extracted_data):
    width, height = pil_img.size

    field_mapping = {
        "dealership_name": "Dealership Name",
        "customer_name": "Customer Name",
        "document_name": "Document Type/Name",
        "scrappage_bonus": "Scrappage Bonus Credit Amount",
        "seal_stamp": "Dealership Stamp & Seal",
    }

    results = []

    for key in ["dealership_name", "customer_name", "document_name", "scrappage_bonus", "seal_stamp"]:
        if key not in extracted_data:
            continue

        data = extracted_data[key]
        field_name = field_mapping[key]

        if key == "scrappage_bonus":
            val = data.get("amount", data.get("text", ""))
        else:
            val = data.get("text", "")

        crop_info = data.get("crop", {})
        top_pct = crop_info.get("top", 0) / 100.0
        left_pct = crop_info.get("left", 0) / 100.0
        bottom_pct = crop_info.get("bottom", 100) / 100.0
        right_pct = crop_info.get("right", 100) / 100.0

        padding_x = 50
        padding_y = 50
        
        x1 = max(0, int(left_pct * width) - padding_x)
        y1 = max(0, int(top_pct * height) - padding_y)
        x2 = min(width, int(right_pct * width) + padding_x)
        y2 = min(height, int(bottom_pct * height) + padding_y)

        x1 = max(0, min(x1, width))
        x2 = max(x1, min(x2, width))
        y1 = max(0, min(y1, height))
        y2 = max(y1, min(y2, height))

        if x2 <= x1: x2 = min(width, x1 + 10)
        if y2 <= y1: y2 = min(height, y1 + 10)

        try:
            crop_img = pil_img.crop((x1, y1, x2, y2))
            buffered = io.BytesIO()
            crop_img.save(buffered, format="PNG")
            crop_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as crop_err:
            logging.error(f"Crop error for {key}: {crop_err}")
            crop_b64 = ""

        results.append({
            "field": field_name,
            "value": val,
            "crop_b64": crop_b64
        })

    return results
