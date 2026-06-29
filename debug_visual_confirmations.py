#!/usr/bin/env python3
"""
Debug script to check why visual confirmations aren't showing.
Run this to diagnose the issue step-by-step.
"""

import json
import os
import sys

print("=" * 70)
print("VISUAL CONFIRMATION DIAGNOSTIC TOOL")
print("=" * 70)
print()

# Step 1: Check if backend was patched
print("STEP 1: Checking if backend code has visual extraction function...")
with open("automate_login.py", "r", encoding="utf-8") as f:
    backend_code = f.read()

if "extract_visual_confirmations" in backend_code:
    print("✅ PASS: Backend has extract_visual_confirmations() function")
else:
    print("❌ FAIL: Backend is NOT patched with visual extraction code")
    print()
    print("FIX: Run this command:")
    print("    python add_visual_confirmation.py")
    print()
    sys.exit(1)

# Step 2: Check if prompt requests bounding boxes
print("\nSTEP 2: Checking if OpenAI prompt requests bounding boxes...")
if "bounding_boxes" in backend_code or "bbox" in backend_code:
    print("✅ PASS: Prompt includes bounding box request")
else:
    print("⚠️  WARNING: Prompt might not request bounding boxes from GPT")
    print("   This could cause visual extractions to be empty")

# Step 3: Check if any JSON files exist with visual_extractions
print("\nSTEP 3: Checking if any processed documents have visual_extractions...")

json_files_found = []
visual_data_found = False

# Check common locations
search_paths = [
    ".",
    "documents",
    "ui_history.json",
]

for path in search_paths:
    if os.path.isfile(path) and path.endswith(".json"):
        json_files_found.append(path)
    elif os.path.isdir(path):
        for file in os.listdir(path):
            if file.endswith(".json"):
                json_files_found.append(os.path.join(path, file))

# Also check ui_history.json specifically
if os.path.exists("ui_history.json"):
    if "ui_history.json" not in json_files_found:
        json_files_found.append("ui_history.json")

print(f"   Found {len(json_files_found)} JSON file(s) to check")

for json_file in json_files_found[:10]:  # Check first 10 files
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check if it's ui_history format
        if isinstance(data, list):
            for item in data:
                docs = item.get("documents", [])
                for doc in docs:
                    extracted = doc.get("extracted_data", {})
                    visual = extracted.get("visual_extractions", {})
                    if visual:
                        visual_data_found = True
                        print(f"✅ FOUND visual_extractions in: {json_file}")
                        print(f"   Fields with visuals: {list(visual.keys())}")

                        # Check if images are actually present
                        for field, vdata in visual.items():
                            if "image_base64" in vdata and vdata["image_base64"]:
                                print(
                                    f"   ✓ {field} has image data ({len(vdata['image_base64'])} bytes)"
                                )
                        break
                if visual_data_found:
                    break

        # Check if it's a single document format
        elif isinstance(data, dict):
            visual = data.get("visual_extractions", {})
            if visual:
                visual_data_found = True
                print(f"✅ FOUND visual_extractions in: {json_file}")
                print(f"   Fields with visuals: {list(visual.keys())}")
    except Exception as e:
        pass

if not visual_data_found:
    print("❌ FAIL: No visual_extractions found in any JSON files")
    print()
    print("This means either:")
    print("  1. You haven't run the automation yet after patching")
    print("  2. GPT-4o-mini is not returning bounding boxes")
    print("  3. The visual extraction function is not being called")
    print()
    print("FIX: Run automation on a test invoice:")
    print("    python automate_login.py")
    print()
    print("Then check if the JSON output has 'visual_extractions' field")
else:
    print("\n✅ Backend is generating visual data correctly!")

# Step 4: Check if UI code has visual panel
print("\nSTEP 4: Checking if UI has visual confirmation panel...")
with open("app_ui.py", "r", encoding="utf-8") as f:
    ui_code = f.read()

if "visual_frame" in ui_code or "Visual Confirmation" in ui_code:
    print("✅ PASS: UI has visual confirmation panel code")

    # Check if it has the display method
    if "load_visual_confirmations" in ui_code:
        print("✅ PASS: UI has load_visual_confirmations() method")
    else:
        print("❌ FAIL: UI missing load_visual_confirmations() method")
        print()
        print("FIX: Add this method to app_ui.py (AppUI class):")
        print("""
def load_visual_confirmations(self, doc_dict):
    # Implementation needed - see VISUAL_CONFIRMATION_GUIDE.md
    pass
""")
else:
    print("❌ FAIL: UI does NOT have visual confirmation panel")
    print()
    print("FIX: You need to manually add the visual panel to app_ui.py")
    print("     See VISUAL_CONFIRMATION_GUIDE.md Step 2")
    print()

# Step 5: Check app_ui_enhanced.py
print("\nSTEP 5: Checking for enhanced UI file...")
if os.path.exists("app_ui_enhanced.py"):
    print("✅ Found app_ui_enhanced.py")
    print("   Try running: python app_ui_enhanced.py")
else:
    print("⚠️  app_ui_enhanced.py not created yet")

print()
print("=" * 70)
print("DIAGNOSTIC SUMMARY")
print("=" * 70)

issues = []
if "extract_visual_confirmations" not in backend_code:
    issues.append("Backend not patched - run: python add_visual_confirmation.py")

if not visual_data_found:
    issues.append("No visual data in JSON files - run automation to generate data")

if "visual_frame" not in ui_code:
    issues.append("UI not updated - manually add visual panel code to app_ui.py")

if not issues:
    print("✅ All checks passed!")
    print()
    print("If you still don't see visuals, the problem might be:")
    print("1. The selected document doesn't have visual_extractions")
    print("2. The UI method isn't being called when selecting a document")
    print("3. Images failed to decode/display")
    print()
    print("Enable debug logging and check for errors in console")
else:
    print("\n❌ Issues found:")
    for i, issue in enumerate(issues, 1):
        print(f"{i}. {issue}")

print()
print("For detailed help, see: VISUAL_CONFIRMATION_GUIDE.md")
print("=" * 70)
