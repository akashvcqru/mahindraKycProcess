#!/usr/bin/env python3
"""
Test visual extraction on a single PDF file.
Usage: python test_single_pdf_visual.py path/to/invoice.pdf
"""

import base64
import io
import json
import os
import sys

from PIL import Image

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

import automate_login


def test_visual_extraction(pdf_path):
    """Test visual extraction on a PDF file."""

    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return

    print(f"Testing visual extraction on: {pdf_path}")
    print("=" * 70)

    # Call the extraction function
    print("\n1. Extracting data with OpenAI Vision...")
    result = automate_login.extract_details_via_openai(pdf_path)

    if not result:
        print("❌ Extraction failed")
        return

    print(f"✅ Extracted data for document type: {result.get('document_type')}")

    # Check visual extractions
    visual = result.get("visual_extractions", {})

    print(f"\n2. Visual extractions: {len(visual)} fields")

    if not visual:
        print("❌ No visual extractions generated")
        print("\nThis could mean:")
        print("  - GPT didn't provide bounding boxes")
        print("  - EasyOCR fallback didn't run")
        print("  - Check logs above for errors")
        return

    print("\n3. Visual confirmation fields:")
    for field_name, vdata in visual.items():
        has_image = "image_base64" in vdata and vdata["image_base64"]
        value = vdata.get("value", "N/A")
        confidence = vdata.get("confidence", 0)
        bbox = vdata.get("bbox", [])

        status = "✅" if has_image else "❌"
        print(f"\n  {status} {field_name}:")
        print(f"      Value: {value}")
        print(f"      Confidence: {confidence}%")
        print(f"      BBox: {bbox}")

        if has_image:
            img_size = len(vdata["image_base64"])
            print(f"      Image: {img_size} bytes (base64)")

            # Try to decode and get dimensions
            try:
                img_bytes = base64.b64decode(vdata["image_base64"])
                img = Image.open(io.BytesIO(img_bytes))
                print(f"      Dimensions: {img.size[0]}x{img.size[1]} pixels")

                # Save for inspection
                output_file = f"visual_{field_name}.png"
                img.save(output_file)
                print(f"      Saved to: {output_file}")
            except Exception as e:
                print(f"      ⚠️ Could not decode image: {e}")

    # Save full result to JSON
    output_json = "test_visual_result.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n4. Full result saved to: {output_json}")
    print("\n" + "=" * 70)
    print("✅ Test complete!")
    print("\nYou can now:")
    print("  1. Open the visual_*.png files to see cropped images")
    print("  2. Run the UI: python app_ui.py")
    print("  3. Process this document and see visuals in the right panel")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Try to find a sample PDF
        sample_pdfs = []
        if os.path.exists("documents"):
            for root, dirs, files in os.walk("documents"):
                for file in files:
                    if file.lower().endswith(".pdf"):
                        sample_pdfs.append(os.path.join(root, file))
                        if len(sample_pdfs) >= 5:
                            break
                if sample_pdfs:
                    break

        if sample_pdfs:
            print("No PDF specified. Using first found PDF:")
            pdf_path = sample_pdfs[0]
            print(f"  {pdf_path}\n")
            test_visual_extraction(pdf_path)
        else:
            print("Usage: python test_single_pdf_visual.py path/to/invoice.pdf")
            print("\nNo sample PDFs found in documents/ folder")
    else:
        test_visual_extraction(sys.argv[1])
