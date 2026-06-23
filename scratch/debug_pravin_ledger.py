"""
Debug script to see what text is actually extracted from PRAVIN's ledger PDF.
"""
import sys, os
sys.path.insert(0, r"c:\Users\admin\Desktop\robbinmahindra")

import logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

from automate_login import extract_text_hybrid, is_narration_in_line, check_amount_match

ledger_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\PRAVIN\PRAVIN  LEDGER-1782131597951.pdf"

print("=" * 60)
print("Extracting text from PRAVIN Ledger PDF...")
print("=" * 60)

text, used_ocr = extract_text_hybrid(ledger_path)

print(f"\nUsed OCR: {used_ocr}")
print(f"Text length: {len(text)} chars")
print("\n--- RAW EXTRACTED TEXT ---")
print(repr(text[:3000]))  # First 3000 chars
print("\n--- LINES ---")
lines = text.split("\n")
print(f"Total lines: {len(lines)}")
for i, line in enumerate(lines):
    if line.strip():
        print(f"  Line {i:3d}: {line}")

print("\n--- NARRATION MATCH TEST ---")
scrappage_kws = ["y scrappage bonus", "scrappage bonus", "scrappage", "y scrappage"]
welcome_kws   = ["welcome bonus", "welcome", "loyalty"]

for line in lines:
    if line.strip():
        if is_narration_in_line(line, scrappage_kws):
            print(f"  SCRAPPAGE MATCH: {line}")
            print(f"    Amount match 30000: {check_amount_match(line, 30000)}")
        if is_narration_in_line(line, welcome_kws):
            print(f"  WELCOME MATCH:   {line}")
            print(f"    Amount match 15000: {check_amount_match(line, 15000)}")

print("\nDone.")
