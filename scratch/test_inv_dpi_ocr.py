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
pix = page.get_pixmap(dpi=300) # 300 DPI like automate_login.py
img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)

# Run EasyOCR
reader = easyocr.Reader(['en'], gpu=False)
results = reader.readtext(img, detail=0)
text = " ".join(results)
print("--- Text extracted at 300 DPI ---")
print(text)
print("---------------------------------")

cleaned_text = text.upper().replace("RORX", "ROXX").replace("ROXX", "ROXX")

# Robust regex allowing letters
amt_match = re.search(
    r'(?:scrappage|welcome|loyalty|exchange)\s+bonus\s+(?:amount\s+)?(?:is\s+)?(?:rs\.?\s*)?([A-Z0-9\.,\s\-]+)',
    cleaned_text,
    re.IGNORECASE
)

def extract_amount_robust(match_str):
    cleaned = match_str.upper()
    for char, replacement in [
        ('O', '0'), ('U', '0'), ('I', '1'), ('L', '1'), ('S', '5'), ('B', '8'), ('Z', '2'), ('G', '6')
    ]:
        cleaned = cleaned.replace(char, replacement)
    
    tokens = [t.strip('.-') for t in re.split(r'[^0-9\.]', cleaned) if t.strip('.-')]
    print(f"Extracted tokens: {tokens}")
    for t in tokens:
        try:
            val = float(t)
            if val >= 1000.0:
                return val
        except ValueError:
            pass
    return None

if amt_match:
    print(f"Regex Match: '{amt_match.group(0)}'")
    print(f"Group 1: '{amt_match.group(1)}'")
    val = extract_amount_robust(amt_match.group(1))
    print(f"Extracted Value: {val}")
else:
    print("No regex match")
