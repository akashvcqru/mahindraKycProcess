import cv2
import fitz
import easyocr
import numpy as np
import os
import sys
import re

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

pdf_path = "documents/G NIVETHA/INV-1781414252482.pdf"
doc = fitz.open(pdf_path)
page = doc.load_page(0)
pix = page.get_pixmap(dpi=300) # 300 DPI for high quality OCR
img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)

h, w, _ = img.shape
print(f"Image size: width={w}, height={h}")

# The bottom section starts around y = 0.6 * h
bottom_y = int(0.6 * h)
bottom_crop = img[bottom_y:h, 0:w]

# Let's save the bottom crop
cv2.imwrite("scratch/inv_bottom_crop.png", bottom_crop)
print("Saved bottom crop to scratch/inv_bottom_crop.png")

# Run EasyOCR on the bottom crop at different angles
reader = easyocr.Reader(['en'], gpu=False)
for angle in [0, 90, 180, 270]:
    if angle == 0:
        rotated = bottom_crop
    elif angle == 90:
        rotated = np.rot90(bottom_crop, k=1)
    elif angle == 180:
        rotated = np.rot90(bottom_crop, k=2)
    elif angle == 270:
        rotated = np.rot90(bottom_crop, k=3)
        
    results = reader.readtext(rotated, detail=0)
    print(f"\n--- Angle {angle} ---")
    print(results)
