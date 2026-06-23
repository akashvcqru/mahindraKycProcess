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

pdf_path = "documents/LANCY BABU P/LANCY LEDGER-1781348080305.pdf"
doc = fitz.open(pdf_path)
page = doc.load_page(0)
pix = page.get_pixmap(dpi=300) # 300 DPI
img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)

# Run EasyOCR
reader = easyocr.Reader(['en'], gpu=False)
results = reader.readtext(img, detail=0)
text = " ".join(results)
print("--- Text extracted at 300 DPI ---")
print(text)
print("---------------------------------")

def find_floats_in_line(line_text):
    cleaned = line_text.lower()
    cleaned = cleaned.replace('(x)', '000').replace('(o)', '000').replace('()', '000')
    cleaned = cleaned.replace('ou', '.00').replace('o0', '.00').replace('oo', '.00')
    cleaned = re.sub(r'[^0-9\.\-]', ' ', cleaned)
    tokens = cleaned.split()
    floats = []
    for t in tokens:
        t = t.strip('.-')
        if not t:
            continue
        if t.count('.') > 1:
            parts = t.split('.')
            t = "".join(parts[:-1]) + "." + parts[-1]
        try:
            floats.append(float(t))
        except ValueError:
            pass
    return floats

def check_amount_match(line_text, target_amount):
    floats = find_floats_in_line(line_text)
    print(f"Floats: {floats}")
    for val in floats:
        if abs(val - target_amount) < 1.0:
            return True
            
    cleaned = line_text.lower()
    cleaned = cleaned.replace('(x)', '000').replace('(o)', '000').replace('()', '000')
    cleaned = cleaned.replace('ou', '00').replace('o0', '00').replace('oo', '00')
    digits = "".join(re.findall(r'\d+', cleaned))
    print(f"Digits: {digits}")
    target_str = str(int(target_amount))
    print(f"Target string: {target_str}")
    if target_str in digits:
        return True
    return False

res = check_amount_match(text, 15000)
print(f"Match result: {res}")
