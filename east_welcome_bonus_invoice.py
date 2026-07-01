import os
import base64
import json
import logging
import io
import fitz
import requests
from PIL import Image

def process_east_welcome_bonus_invoice(pdf_path):
    """
    Processes an invoice PDF specifically for the East Zone Welcome Bonus scheme.
    Extracts 7 specific fields using OpenAI Vision and provides approximate visual crops
    for the UI.
    """
    logging.info(f"Processing East Welcome Bonus Invoice: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        logging.error("Invoice PDF not found.")
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

    prompt_text = """You are an advanced document analysis AI. Your task is to read this tax invoice image line by line from top to bottom.

Extract ONLY the following 7 fields in exact order:
1. Dealership Name (from the header at the very top)
2. Document Type (Tax Invoice / GST Invoice label)
3. GST Invoice Number and Date
4. Customer Name (exactly as printed)
5. OEM Loyalty Discount or Welcome Bonus Discount amount
6. Customer Signature (Status: Present/Missing, and does it match the name?)
7. Dealership Stamp and Seal (Printed name, designation, reverse charge status)

OUTPUT FORMAT:
Return a strictly valid JSON array containing exactly 7 objects. 
Each object must have "field" and "value" keys.
Do not include markdown blocks, explanations, or extra text.
Example:
[
  {"field": "Dealership Name", "value": "Example Motors Ltd"},
  ...
]"""

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
        {"field": "Dealership Name", "value": "Error connecting to LLM"},
        {"field": "Document Type", "value": "Error connecting to LLM"},
        {"field": "GST Invoice Number and Date", "value": "Error connecting to LLM"},
        {"field": "Customer Name", "value": "Error connecting to LLM"},
        {"field": "OEM Loyalty Discount / Welcome Bonus", "value": "Error connecting to LLM"},
        {"field": "Customer Signature", "value": "Error connecting to LLM"},
        {"field": "Dealership Stamp & Seal", "value": "Error connecting to LLM"}
    ]
    return pair_crops_with_data(pil_img, mock_data)


def pair_crops_with_data(pil_img, extracted_data):
    """
    Slices the image into 7 approximate regions for the UI, focusing on the particular text area.
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
    
    # Approximate vertical regions as percentages (top, bottom) for Invoice fields as fallbacks
    crop_regions = [
        (0.00, 0.15),  # 1. Dealership Name
        (0.10, 0.20),  # 2. Document Type
        (0.15, 0.30),  # 3. GST Invoice Number and Date
        (0.20, 0.35),  # 4. Customer Name
        (0.40, 0.70),  # 5. OEM Loyalty Discount / Welcome Bonus Discount
        (0.75, 1.00),  # 6. Customer Signature
        (0.75, 1.00),  # 7. Dealership Stamp and Seal
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
                if "signature" in field.lower() or "stamp" in field.lower() or "seal" in field.lower() or i >= 5:
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
        
    return results

if __name__ == "__main__":
    pass
