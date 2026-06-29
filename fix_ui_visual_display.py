#!/usr/bin/env python3
"""
Script to verify and fix UI visual display issues.
"""

import os

print("Checking UI visual display setup...")
print("=" * 70)

# Read the UI file
with open("app_ui.py", "r", encoding="utf-8") as f:
    ui_code = f.read()

issues_found = []

# Check 1: Visual panel exists
if "self.visual_panel" not in ui_code:
    issues_found.append("❌ Visual panel not defined")
else:
    print("✅ Visual panel exists")

# Check 2: Visual frame exists
if "self.visual_frame" not in ui_code:
    issues_found.append("❌ Visual frame not defined")
else:
    print("✅ Visual frame exists")

# Check 3: load_visual_confirmations method exists
if "def load_visual_confirmations" not in ui_code:
    issues_found.append("❌ load_visual_confirmations method missing")
else:
    print("✅ load_visual_confirmations method exists")

# Check 4: Method is being called
if "self.load_visual_confirmations" not in ui_code:
    issues_found.append("❌ load_visual_confirmations is not being called anywhere")
else:
    print("✅ load_visual_confirmations is called")
    # Count how many times
    count = ui_code.count("self.load_visual_confirmations")
    print(f"   Called {count} time(s)")

# Check 5: Import statements
if "import base64" not in ui_code or "from PIL import Image" not in ui_code:
    issues_found.append("⚠️  Missing imports for image handling")
else:
    print("✅ Image handling imports present")

# Check 6: extraction_images list
if "self.extraction_images" not in ui_code:
    issues_found.append("❌ extraction_images list not initialized")
else:
    print("✅ extraction_images list exists")

print()
if issues_found:
    print("ISSUES FOUND:")
    for issue in issues_found:
        print(f"  {issue}")
else:
    print("✅ All basic checks passed!")
    print()
    print("The UI code looks correct. The problem might be:")
    print("  1. Visual extractions data is empty in the processed claims")
    print("  2. There's a runtime error when displaying images")
    print("  3. The visual panel is hidden or not properly shown")
    print()
    print("Next step: Add debug logging to the UI")

print()
print("=" * 70)
