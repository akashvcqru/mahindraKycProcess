import os
import fitz
import easyocr
import numpy as np
import cv2

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\CAMS SHADES\DIS_INV-1782121114735.pdf"
doc = fitz.open(pdf_path)
reader = easyocr.Reader(['en'], gpu=False)

for i in range(len(doc)):
    page = doc.load_page(i)
    pix = page.get_pixmap(dpi=150)
    img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
    results = reader.readtext(img, detail=0)
    text = " ".join(results)
    print(f"\n--- PAGE {i+1} OCR TEXT ---")
    print(text[:1000])
