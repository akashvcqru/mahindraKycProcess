#!/usr/bin/env python3
"""
New visual extraction using object detection prompt.
This replaces the old approach with a more reliable method.
"""

import base64
import io
import json
import logging
import os
import sys

import fitz
import requests
from PIL import Image


def extract_visual_with_object_detection(pdf_path):
    """
    Extract visual confirmations using object detection prompt.
    Returns bounding boxes for stamps, signatures, invoice numbers, etc.
    """

    # Convert PDF to base64 image
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=300)
    png_bytes = pix.tobytes("png")
    b64_image = base64.b64encode(png_bytes).decode("utf-8")

    # Get image dimensions
    img = Image.open(io.BytesIO(png_bytes))
    img_width, img_height = img.size

    # Object detection prompt
    prompt = """Analyze the provided document image and detect the following objects:

1. Handwritten Signature
2. Company Stamp
3. Customer Handwritten Name
4. Printed Customer Name
5. Invoice Number
6. Chassis Number
7. Date
8. Dealer Name/Stamp

For each detected object return:
- object_type
- found (true/false)
- confidence (0.0 to 1.0)
- bounding_box (x, y, width, height in pixels)
- description

IMPORTANT:
- Coordinates MUST be in pixels relative to the ORIGINAL uploaded image.
- (0,0) is the top-left corner.
- Bounding boxes should tightly enclose the object.
- If an object is not present, return found=false and bounding_box=null.
- Return JSON only.
- Do not include markdown.

JSON Schema:
{
  "image_width": 0,
  "image_height": 0,
  "objects": [
    {
      "object_type": "signature",
      "found": true,
      "confidence": 0.98,
      "bounding_box": {"x": 0, "y": 0, "width": 0, "height": 0},
      "description": "Blue handwritten signature."
    }
  ]
}"""

    # Call OpenAI API
    api_key = os.getenv("OPENAI_API_KEY", "")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    payload = {
        "model": "gpt-4o-mini",
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                    },
                ],
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.0,
    }

    try:
        print("Calling GPT-4o-mini for object detection...")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]
        detection_result = json.loads(content)

        print(
            f"✅ Detection complete: {len(detection_result.get('objects', []))} objects"
        )

        # Crop images for each detected object
        visual_extractions = {}

        for obj in detection_result.get("objects", []):
            if not obj.get("found", False):
                continue

            bbox = obj.get("bounding_box")
            if not bbox:
                continue

            obj_type = obj.get("object_type", "unknown")

            # Crop the region
            x = bbox["x"]
            y = bbox["y"]
            w = bbox["width"]
            h = bbox["height"]

            # Ensure within bounds
            x = max(0, min(x, img_width))
            y = max(0, min(y, img_height))
            w = min(w, img_width - x)
            h = min(h, img_height - y)

            cropped = img.crop((x, y, x + w, y + h))

            # Convert to base64
            buffered = io.BytesIO()
            cropped.save(buffered, format="PNG")
            img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # Map object_type to field names
            field_mapping = {
                "signature": "customer_signature",
                "handwritten_signature": "customer_signature",
                "company_stamp": "seal_stamp_dealer_name",
                "stamp": "seal_stamp_dealer_name",
                "invoice_number": "invoice_number",
                "chassis_number": "chassis_number",
                "date": "invoice_date",
                "customer_name": "customer_name",
                "dealer_name": "seal_stamp_dealer_name",
            }

            field_name = field_mapping.get(obj_type.lower(), obj_type)

            visual_extractions[field_name] = {
                "value": obj.get("description", ""),
                "confidence": int(obj.get("confidence", 0) * 100),
                "bbox": [x, y, x + w, y + h],
                "image_base64": img_b64,
            }

            print(f"  ✓ Cropped {obj_type}: {w}x{h} pixels")

        return visual_extractions

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return {}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Find a sample PDF
        for root, dirs, files in os.walk("documents"):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_path = os.path.join(root, file)
                    print(f"Testing with: {pdf_path}\n")

                    result = extract_visual_with_object_detection(pdf_path)

                    print(f"\n✅ Extracted {len(result)} visual confirmations:")
                    for field, data in result.items():
                        print(f"  - {field}: {data['confidence']}% confidence")

                    # Save to JSON
                    with open("object_detection_result.json", "w") as f:
                        json.dump(result, f, indent=2)
                    print("\nSaved to: object_detection_result.json")

                    # Save cropped images
                    for field, data in result.items():
                        img_bytes = base64.b64decode(data["image_base64"])
                        img = Image.open(io.BytesIO(img_bytes))
                        img.save(f"detected_{field}.png")
                        print(f"Saved: detected_{field}.png")

                    break
            break
    else:
        pdf_path = sys.argv[1]
        result = extract_visual_with_object_detection(pdf_path)
        print(json.dumps(result, indent=2))
