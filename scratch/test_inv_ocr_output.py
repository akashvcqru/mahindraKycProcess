import os
import sys
import cv2
import numpy as np
import fitz
import easyocr
import re
from pypdf import PdfReader

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

pdf_path = "documents/G NIVETHA/INV-1781414252482.pdf"
doc = fitz.open(pdf_path)
page = doc.load_page(0)
pix = page.get_pixmap(dpi=150)
img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)

# Run EasyOCR
reader = easyocr.Reader(['en'], gpu=False)
results = reader.readtext(img, detail=0)
text = " ".join(results)
print("--- Text extracted ---")
print(text)
print("----------------------")

# Let's test the regex
cleaned_text = text.upper().replace("RORX", "ROXX").replace("ROXX", "ROXX")

# Let's see what is matched
amt_match = re.search(
    r'(?:scrappage|welcome|loyalty|exchange)\s+bonus\s+(?:amount\s+)?(?:is\s+)?(?:rs\.?\s*)?([\d\.,oOu\s]+)',
    cleaned_text,
    re.IGNORECASE
)
if amt_match:
    print(f"Match: '{amt_match.group(0)}'")
    print(f"Group 1: '{amt_match.group(1)}'")
    # clean OCR digits
    amt_str = amt_match.group(1)
    amt_str = amt_str.replace('O', '0').replace('o', '0').replace('u', '0').replace(' ', '')
    amt_str = ''.join(c for c in amt_str if c.isdigit() or c == '.')
    print(f"Cleaned string: '{amt_str}'")
    try:
        val = float(amt_str)
        print(f"Value: {val}")
    except ValueError:
        print("Value conversion failed")
else:
    print("No regex match")
