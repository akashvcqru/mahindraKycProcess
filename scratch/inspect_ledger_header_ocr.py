import cv2
import numpy as np
import fitz
import easyocr
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\ABILASHGOWDA A\LEDGER -1781516436504.pdf"
print("Loading EasyOCR...")
reader = easyocr.Reader(['en'], gpu=False)

print(f"Opening PDF: {pdf_path}")
doc = fitz.open(pdf_path)
page = doc[0]
pix = page.get_pixmap(dpi=300)
img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
h, w, _ = img.shape

# Crop top 35%
header_crop = img[0:int(0.35 * h), 0:w]
print("Running OCR on top 35%...")
results = reader.readtext(header_crop, detail=0)
print("\n--- OCR TEXT ---")
print(" ".join(results))
print("----------------")
