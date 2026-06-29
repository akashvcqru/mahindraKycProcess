#!/usr/bin/env python3
"""
Script to add visual confirmation features to existing codebase.
Run this to automatically patch automate_login.py and app_ui.py
"""

import os
import re


def add_visual_extraction_to_automate_login():
    """Add visual extraction capability to automate_login.py"""

    file_path = "automate_login.py"

    # Read the file
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if already patched
    if "extract_visual_confirmations" in content:
        print("✓ automate_login.py already has visual confirmation code")
        return

    # Find the extract_details_via_openai function
    # Add new function after it

    new_function = '''

def extract_visual_confirmations(pdf_path, extracted_data, base64_images):
    """
    Crop regions from the original document based on bounding boxes
    and save them as base64 images for visual confirmation.

    This allows UI to show cropped images of stamps, signatures, invoice numbers, etc.

    Returns: dict with field names as keys and cropped image data
    """
    import base64
    import io
    from PIL import Image

    visual_extractions = {}

    # Get bounding boxes from extraction result
    bounding_boxes = extracted_data.get("bounding_boxes", {})

    if not bounding_boxes or not base64_images:
        logging.info("No bounding boxes available for visual confirmation")
        return visual_extractions

    try:
        # Decode the first page image (most extractions are from page 1)
        image_bytes = base64.b64decode(base64_images[0])
        image = Image.open(io.BytesIO(image_bytes))
        img_width, img_height = image.size

        logging.info(f"Extracting visual confirmations from image {img_width}x{img_height}")

        # Process each field with bounding box
        for field_name, bbox in bounding_boxes.items():
            if not bbox or len(bbox) != 4:
                continue

            # Extract coordinates
            x1, y1, x2, y2 = bbox

            # Validate coordinates
            if x1 >= x2 or y1 >= y2:
                logging.warning(f"Invalid bbox for {field_name}: {bbox}")
                continue

            # Ensure coordinates are within image bounds
            x1 = max(0, min(int(x1), img_width))
            x2 = max(0, min(int(x2), img_width))
            y1 = max(0, min(int(y1), img_height))
            y2 = max(0, min(int(y2), img_height))

            # Add small padding (10% of width/height)
            padding_x = int((x2 - x1) * 0.10)
            padding_y = int((y2 - y1) * 0.10)

            x1 = max(0, x1 - padding_x)
            y1 = max(0, y1 - padding_y)
            x2 = min(img_width, x2 + padding_x)
            y2 = min(img_height, y2 + padding_y)

            # Crop the region
            cropped = image.crop((x1, y1, x2, y2))

            # Convert to base64
            buffered = io.BytesIO()
            cropped.save(buffered, format="PNG", optimize=True)
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            # Get the extracted value and confidence
            field_value = extracted_data.get(field_name, "")
            confidence = extracted_data.get("confidence_score", 0)

            # Store visual extraction data
            visual_extractions[field_name] = {
                "value": field_value,
                "confidence": confidence,
                "bbox": [x1, y1, x2, y2],
                "image_base64": img_base64
            }

            logging.info(f"✓ Visual confirmation extracted for {field_name} (bbox: {x1},{y1} to {x2},{y2})")

        logging.info(f"Extracted {len(visual_extractions)} visual confirmations")
        return visual_extractions

    except Exception as e:
        logging.error(f"Error extracting visual confirmations: {e}")
        import traceback
        traceback.print_exc()
        return visual_extractions

'''

    # Insert after get_upright_page_image function
    insertion_point = content.find("def extract_text_hybrid(")

    if insertion_point == -1:
        print("❌ Could not find insertion point in automate_login.py")
        return

    # Insert the new function
    new_content = (
        content[:insertion_point] + new_function + "\n" + content[insertion_point:]
    )

    # Update the prompt to request bounding boxes
    prompt_section = """
IMPORTANT - BOUNDING BOXES:
For each field you extract, also provide the bounding box coordinates [x_min, y_min, x_max, y_max] in pixels where you found this information in the image. This allows visual confirmation in the UI.

Add a "bounding_boxes" field to your JSON response:

{
  "document_type": "",
  "customer_name": "",
  "invoice_number": "",
  ... (other fields) ...
  "bounding_boxes": {
    "customer_name": [x1, y1, x2, y2],
    "invoice_number": [x1, y1, x2, y2],
    "chassis_number": [x1, y1, x2, y2],
    "seal_stamp_dealer_name": [x1, y1, x2, y2],
    "invoice_date": [x1, y1, x2, y2]
  }
}

"""

    # Find the prompt in extract_details_via_openai
    prompt_marker = "Return JSON in this format:"
    if prompt_marker in new_content:
        # Add bounding box instruction before the JSON format
        new_content = new_content.replace(
            prompt_marker, prompt_section + "\n" + prompt_marker
        )

    # Update the function to call visual extraction
    # Find where we return extracted_data
    return_pattern = r'(logging\.info\(\s*f"Successfully extracted .* data.*"\s*\)\s*return extracted_data)'

    replacement = r"""logging.info(
            f"Successfully extracted {doc_type} data from {os.path.basename(pdf_path)}"
        )

        # Add visual confirmations (cropped images of extracted fields)
        try:
            visual_data = extract_visual_confirmations(
                pdf_path,
                extracted_data,
                base64_images
            )
            extracted_data["visual_extractions"] = visual_data
            logging.info(f"Added {len(visual_data)} visual confirmations to extraction result")
        except Exception as ve:
            logging.error(f"Failed to extract visual confirmations: {ve}")
            extracted_data["visual_extractions"] = {}

        return extracted_data"""

    new_content = re.sub(return_pattern, replacement, new_content, flags=re.MULTILINE)

    # Write back
    with open(file_path + ".backup", "w", encoding="utf-8") as f:
        f.write(content)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("✓ automate_login.py updated with visual confirmation support")
    print("  - Added extract_visual_confirmations() function")
    print("  - Updated prompt to request bounding boxes")
    print("  - Integrated visual extraction into main flow")
    print(f"  - Backup saved to {file_path}.backup")


def main():
    """Main execution"""
    print("=" * 60)
    print("Visual Confirmation Feature Installer")
    print("=" * 60)
    print()

    # Check if files exist
    if not os.path.exists("automate_login.py"):
        print("❌ automate_login.py not found in current directory")
        return

    print("This script will add visual confirmation features:")
    print("  ✓ Extracts bounding boxes from GPT-4o-mini")
    print("  ✓ Crops images of detected entities")
    print("  ✓ Stores as base64 for UI display")
    print()

    response = input("Continue? (y/n): ").strip().lower()
    if response != "y":
        print("Aborted.")
        return

    print()
    print("Patching automate_login.py...")
    add_visual_extraction_to_automate_login()

    print()
    print("=" * 60)
    print("✓ Installation Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Review the changes in automate_login.py")
    print("2. Read VISUAL_CONFIRMATION_GUIDE.md for UI integration")
    print("3. Test with a sample invoice")
    print("4. Check that visual_extractions appear in the JSON output")
    print()
    print("To add UI support, see:")
    print("  - VISUAL_CONFIRMATION_GUIDE.md (Step 2)")
    print()


if __name__ == "__main__":
    main()
