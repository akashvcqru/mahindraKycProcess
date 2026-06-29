#!/usr/bin/env python3
"""
Quick test to verify visual extraction is working with EasyOCR fallback.
"""

import json
import os
import sys

# Check if we have any processed JSON files
print("Checking for processed documents...")

if os.path.exists("ui_history.json"):
    with open("ui_history.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Found {len(data)} processed claims")

    # Check first claim
    if data:
        first_claim = data[0]
        docs = first_claim.get("documents", [])

        print(f"\nFirst claim has {len(docs)} documents")

        for i, doc in enumerate(docs):
            print(f"\nDocument {i + 1}:")
            print(f"  Type: {doc.get('file_type')}")
            print(f"  Path: {doc.get('file_path')}")

            extracted = doc.get("extracted_data", {})
            visual = extracted.get("visual_extractions", {})

            print(f"  Visual extractions: {len(visual)} fields")

            if visual:
                print("  Fields with images:")
                for field, vdata in visual.items():
                    has_image = "image_base64" in vdata and vdata["image_base64"]
                    status = "✅" if has_image else "❌"
                    print(f"    {status} {field}")
            else:
                print("  ⚠️ No visual extractions found")
                print("\n  This means:")
                print("    1. GPT-4o-mini didn't return bounding boxes")
                print("    2. EasyOCR fallback might not have run")
                print("    3. Or the document wasn't processed with the new code")
                print("\n  Solution: Run automation again to regenerate data")
else:
    print("No ui_history.json found. Run automation first.")
