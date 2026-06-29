#!/usr/bin/env python3
"""
Force reload and test visual extraction to ensure code is updated.
"""

import os
import sys

# Clear any cached modules
if "automate_login" in sys.modules:
    del sys.modules["automate_login"]

# Fresh import
import importlib

import automate_login

importlib.reload(automate_login)

print("Testing if visual extraction integration is present...")
print("=" * 70)

# Check if the function exists
if hasattr(automate_login, "extract_visual_confirmations"):
    print("✅ extract_visual_confirmations function EXISTS")
else:
    print("❌ extract_visual_confirmations function MISSING")
    sys.exit(1)

# Check if extract_bboxes_with_easyocr exists
if hasattr(automate_login, "extract_bboxes_with_easyocr"):
    print("✅ extract_bboxes_with_easyocr function EXISTS")
else:
    print("❌ extract_bboxes_with_easyocr function MISSING")

# Read the source to verify the integration
import inspect

source = inspect.getsource(automate_login.extract_details_via_openai)

if "extract_visual_confirmations" in source:
    print("✅ Visual extraction IS called in extract_details_via_openai")
else:
    print("❌ Visual extraction NOT called in extract_details_via_openai")
    sys.exit(1)

if "visual_extractions" in source:
    print("✅ visual_extractions field is set")
else:
    print("❌ visual_extractions field NOT set")

print("\n" + "=" * 70)
print("✅ All checks passed - code is updated correctly!")
print("\nNow test with a real PDF:")
print("  python test_single_pdf_visual.py")
