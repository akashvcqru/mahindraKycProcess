import os
import base64
import json
import logging
import io
import fitz
import requests
import re
from datetime import datetime
from PIL import Image

def process_east_welcome_bonus_disclaimer(pdf_path):
    """
    Processes a disclaimer PDF specifically for the East Zone Welcome Bonus scheme.
    Extracts 9 specific fields using OpenAI Vision and provides approximate visual crops
    for the UI.
    """
    logging.info(f"Processing East Welcome Bonus Disclaimer: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        logging.error("Disclaimer PDF not found.")
        return []

    try:
        # Convert first page of PDF to image
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200)
        png_bytes = pix.tobytes("png")
        pil_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    except Exception as e:
        logging.error(f"Failed to render PDF {pdf_path}: {e}")
        return []

    # Encode full image for OpenAI
    img_byte_arr = io.BytesIO()
    pil_img.save(img_byte_arr, format="PNG")
    full_b64 = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")

    prompt_text = """You are a document analysis expert. Read this Customer Disclaimer document image line by line from top to bottom.

Extract ONLY these 9 fields in exact order:
1. Dealership Name from the heading/banner at the very top of the document
2. Document Title (the bold centered heading)
3. Document Issue Date (shown as "Date:" on the top-left below the title)
4. Dealership Name as written inside the paragraph body text (after "Dealership name")
5. New Vehicle Model name (after "Buying New Vehicle Model")
6. Chassis Number ONLY (after "Chassis no" — do NOT include Engine no)
7. Invoice Number and Invoice Date (after "Invoice No" and "Invoice Date")
8. Dealership Stamp and Seal details — name printed, designation, and label at bottom left
9. Customer Name (printed below signature) and whether a manual handwritten signature is present above it

Return ONLY a valid JSON array with exactly 9 objects in this format:
[
  {"field": "...", "value": "..."},
  ...
]

No extra text. No markdown. No explanation. Return only the raw JSON array."""

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logging.error("OPENAI_API_KEY not found in environment.")
        return generate_mock_response(pil_img)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt_text
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{full_b64}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1500,
        "temperature": 0.0
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        resp_json = response.json()
        content = resp_json["choices"][0]["message"]["content"]
        
        # Clean markdown
        content = content.replace("```json", "").replace("```", "").strip()
        extracted_data = json.loads(content)
        
    except Exception as e:
        logging.error(f"OpenAI API call failed or returned invalid JSON: {e}")
        return generate_mock_response(pil_img)

    return pair_crops_with_data(pil_img, extracted_data)


def generate_mock_response(pil_img):
    """Fallback if API fails, generates empty results with crops."""
    mock_data = [
        {"field": "1. Dealership Name (Heading)", "value": "Error connecting to LLM"},
        {"field": "2. Document Title", "value": "Error connecting to LLM"},
        {"field": "3. Document Issue Date", "value": "Error connecting to LLM"},
        {"field": "4. Dealership Name (Body)", "value": "Error connecting to LLM"},
        {"field": "5. New Vehicle Model", "value": "Error connecting to LLM"},
        {"field": "6. Chassis Number", "value": "Error connecting to LLM"},
        {"field": "7. Invoice No & Date", "value": "Error connecting to LLM"},
        {"field": "8. Dealership Stamp & Seal", "value": "Error connecting to LLM"},
        {"field": "9. Customer Name & Signature", "value": "Error connecting to LLM"}
    ]
    return pair_crops_with_data(pil_img, mock_data)

def perform_date_validation(extracted_data):
    issue_date = None
    invoice_date = None
    
    def parse_date(date_str):
        if not date_str:
            return None
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
            "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
            "%Y-%m-%d", "%Y/%m/%d",
            "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%B-%Y",
            "%d %b %y", "%d %B %y", "%d-%b-%y", "%d-%B-%y"
        ]
        matches = re.findall(r'\b\d{1,4}[/\-\. a-zA-Z]+\d{2,4}\b', date_str)
        for match in matches:
            match = re.sub(r'\s+', ' ', match.strip())
            for fmt in formats:
                try:
                    return datetime.strptime(match, fmt)
                except ValueError:
                    continue
        return None

    for item in extracted_data:
        field = item.get("field", "")
        val = item.get("value", "")
        if "3." in field or "Issue Date" in field:
            issue_date = parse_date(val)
        elif "7." in field or "Invoice" in field:
            invoice_date = parse_date(val)
            
    if issue_date and invoice_date:
        if issue_date >= invoice_date:
            return {"field": "Validation: Date Check", "value": f"MATCH: Disclaimer Issue Date ({issue_date.strftime('%Y-%m-%d')}) is >= Invoice Date ({invoice_date.strftime('%Y-%m-%d')}).", "crop_b64": ""}
        else:
            return {"field": "Validation: Date Check", "value": f"MISMATCH: Disclaimer Issue Date ({issue_date.strftime('%Y-%m-%d')}) is BEFORE Invoice Date ({invoice_date.strftime('%Y-%m-%d')})!", "crop_b64": ""}
    
    return {"field": "Validation: Date Check", "value": f"WARNING: Could not parse both dates to perform validation. (Issue: {issue_date}, Invoice: {invoice_date})", "crop_b64": ""}

def pair_crops_with_data(pil_img, extracted_data):
    """
    Slices the image into 9 approximate regions for the UI, focusing on the particular text area.
    """
    import numpy as np
    import easyocr
    from rapidfuzz import fuzz
    
    width, height = pil_img.size
    
    # Run EasyOCR once on the full page image
    raw_results = []
    try:
        reader = easyocr.Reader(['en'], gpu=False)
        img_np = np.array(pil_img)
        raw_results = reader.readtext(img_np)
    except Exception as e:
        logging.warning(f"Failed to run EasyOCR for crops: {e}")
    
    # Approximate vertical regions as percentages (top, bottom) as fallbacks
    crop_regions = [
        (0.00, 0.15),  # 1. Dealership Heading
        (0.10, 0.22),  # 2. Document Title
        (0.15, 0.28),  # 3. Document Date
        (0.25, 0.45),  # 4. Dealership Name (Body)
        (0.35, 0.55),  # 5. New Vehicle Model
        (0.45, 0.65),  # 6. Chassis Number
        (0.50, 0.75),  # 7. Invoice Number and Date
        (0.70, 1.00),  # 8. Stamp & Seal
        (0.70, 1.00),  # 9. Signature
    ]
    
    results = []
    for i, data in enumerate(extracted_data):
        val = data.get("value", "")
        field = data.get("field", "")
        
        crop_img = None
        
        # Try to locate the particular text area of the value
        best_score = 0
        best_box = None
        target_clean = "".join([c for c in val.lower() if c.isalnum() or c.isspace()]).strip()
        
        if target_clean and len(target_clean) >= 2 and raw_results:
            for bbox, text, conf in raw_results:
                text_clean = "".join([c for c in text.lower() if c.isalnum() or c.isspace()]).strip()
                if not text_clean:
                    continue
                score = fuzz.partial_ratio(target_clean, text_clean)
                if score > best_score:
                    best_score = score
                    best_box = bbox
                    
        if best_box and best_score > 70:
            try:
                x_coords = [p[0] for p in best_box]
                y_coords = [p[1] for p in best_box]
                x1 = max(0, min(x_coords) - 15)
                y1 = max(0, min(y_coords) - 15)
                x2 = min(width, max(x_coords) + 15)
                y2 = min(height, max(y_coords) + 15)
                
                # Expand signature or stamp crops
                if "signature" in field.lower() or "stamp" in field.lower() or "seal" in field.lower() or i >= 7:
                    y1 = max(0, y1 - 80)
                    y2 = min(height, y2 + 80)
                    x1 = max(0, x1 - 50)
                    x2 = min(width, x2 + 50)
                    
                crop_img = pil_img.crop((x1, y1, x2, y2))
            except Exception as crop_err:
                logging.warning(f"Fuzzy crop failed: {crop_err}")
                
        # Fallback to horizontal slice if fuzzy crop is not available
        if crop_img is None and i < len(crop_regions):
            top_pct, bot_pct = crop_regions[i]
            box = (0, int(height * top_pct), width, int(height * bot_pct))
            crop_img = pil_img.crop(box)
            
        if crop_img:
            # Encode crop to base64
            buffered = io.BytesIO()
            crop_img.save(buffered, format="PNG")
            crop_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        else:
            crop_b64 = ""
            
        results.append({
            "field": field,
            "value": val,
            "crop_b64": crop_b64
        })
        
    val_res = perform_date_validation(extracted_data)
    if val_res:
        results.append(val_res)
        
    return results

if __name__ == "__main__":
    # Test script locally
    # results = process_east_welcome_bonus_disclaimer("some_file.pdf")
    # print(json.dumps(results, indent=2))
    pass
