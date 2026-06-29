import os
import base64
import json
import logging
import io
import fitz
import requests
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
        "model": "gpt-4o",
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

def pair_crops_with_data(pil_img, extracted_data):
    """
    Slices the image into 9 approximate regions for the UI.
    """
    width, height = pil_img.size
    
    # Approximate vertical regions as percentages (top, bottom)
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
        if i < len(crop_regions):
            top_pct, bot_pct = crop_regions[i]
            box = (0, int(height * top_pct), width, int(height * bot_pct))
            crop_img = pil_img.crop(box)
            
            # Encode crop to base64
            buffered = io.BytesIO()
            crop_img.save(buffered, format="PNG")
            crop_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        else:
            crop_b64 = ""
            
        results.append({
            "field": data.get("field", f"Field {i+1}"),
            "value": data.get("value", ""),
            "crop_b64": crop_b64
        })
        
    return results

if __name__ == "__main__":
    # Test script locally
    # results = process_east_welcome_bonus_disclaimer("some_file.pdf")
    # print(json.dumps(results, indent=2))
    pass
