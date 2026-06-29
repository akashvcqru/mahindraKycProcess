#!/usr/bin/env python3
"""
Create a test claim with visual extractions to verify UI display works.
This bypasses the automation and directly creates test data.
"""

import base64
import io
import json

from PIL import Image, ImageDraw, ImageFont

print("Creating test visual data...")


# Create a simple test image
def create_test_image(text, width=200, height=60):
    """Create a simple test image with text."""
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    # Draw a border
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline="black", width=2)

    # Draw text
    try:
        draw.text((10, 20), text, fill="black")
    except:
        # If font fails, just use default
        pass

    # Convert to base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# Create test visual extractions
test_visual_data = {
    "invoice_number": {
        "value": "TEST-INV-12345",
        "confidence": 95,
        "bbox": [100, 50, 300, 80],
        "image_base64": create_test_image("TEST-INV-12345"),
    },
    "chassis_number": {
        "value": "MA1TEST123456789",
        "confidence": 92,
        "bbox": [100, 100, 300, 130],
        "image_base64": create_test_image("MA1TEST123456789"),
    },
    "customer_name": {
        "value": "TEST CUSTOMER",
        "confidence": 88,
        "bbox": [100, 150, 300, 180],
        "image_base64": create_test_image("TEST CUSTOMER"),
    },
    "seal_stamp_dealer_name": {
        "value": "Test Motors Ltd",
        "confidence": 85,
        "bbox": [100, 200, 250, 280],
        "image_base64": create_test_image("Test Motors\nLtd", height=80),
    },
}

# Create a test claim
test_claim = {
    "row_idx": 999,
    "customer_name": "TEST CUSTOMER (Visual Test)",
    "status": "APPROVED",
    "issues": [],
    "claim_date": "2026-06-27",
    "documents": [
        {
            "file_type": "INVOICE",
            "file_name": "TEST_INVOICE.pdf",
            "file_path": "test.pdf",
            "extracted_data": {
                "document_type": "INVOICE",
                "invoice_number": "TEST-INV-12345",
                "chassis_number": "MA1TEST123456789",
                "customer_name": "TEST CUSTOMER",
                "seal_stamp_dealer_name": "Test Motors Ltd",
                "confidence_score": 90,
                "visual_extractions": test_visual_data,
            },
            "validations": {
                "Invoice Number Match": "MATCH (Test)",
                "Customer Name Match": "MATCH (Test)",
            },
        }
    ],
}

# Load existing history or create new
try:
    with open("ui_history.json", "r", encoding="utf-8") as f:
        history = json.load(f)
except:
    history = []

# Add test claim at the beginning
history.insert(0, test_claim)

# Save
with open("ui_history.json", "w", encoding="utf-8") as f:
    json.dump(history, f, indent=2, ensure_ascii=False)

print("✅ Test visual data created!")
print("\nNow:")
print("1. Run: python app_ui.py")
print("2. Click on the FIRST row (TEST CUSTOMER)")
print("3. Look at the RIGHT PANEL - you should see 4 visual cards!")
print("\nIf you see the test images, the UI is working correctly.")
print("If not, check console for error messages.")
