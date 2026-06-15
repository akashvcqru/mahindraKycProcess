import re
import cv2
import fitz
import easyocr
from rapidfuzz import fuzz
import numpy as np
import os
import sys

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def analyze_pdf_color_and_text(pdf_path, company_name):
    print(f"Analyzing {os.path.basename(pdf_path)}...")
    doc = fitz.open(pdf_path)
    print(f"Number of pages: {len(doc)}")
    
    # Let's inspect page 0
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=300)
    img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Blue/purple color range
    lower_blue = np.array([90, 50, 50])
    upper_blue = np.array([130, 255, 255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    
    blue_pixels = np.sum(mask > 0)
    print(f"Blue/purple pixels: {blue_pixels}")
    
    if blue_pixels < 100:
        print("Very few blue/purple pixels detected. Checking other ink colors or lower threshold...")
        # Let's check if there are other ink colors or if we should use a wider mask
        # e.g., black ink signature, or if the stamp is blue/purple
        
    if blue_pixels > 0:
        pts = np.argwhere(mask > 0)
        ymin, xmin = pts.min(axis=0)
        ymax, xmax = pts.max(axis=0)
        print(f"Blue bounding box: ymin={ymin}, xmin={xmin}, ymax={ymax}, xmax={xmax}")
        
        # Let's crop it and write to file to inspect or OCR
        h, w, _ = img.shape
        crop_ymin = max(0, ymin - 20)
        crop_ymax = min(h, ymax + 20)
        crop_xmin = max(0, xmin - 20)
        crop_xmax = min(w, xmax + 20)
        crop = img[crop_ymin:crop_ymax, crop_xmin:crop_xmax]
        cv2.imwrite("scratch/inv_stamp_crop.png", crop)
        print("Wrote crop to scratch/inv_stamp_crop.png")
        
        # EasyOCR on the crop
        reader = easyocr.Reader(['en'], gpu=False)
        stamp_words = []
        for angle in [0, 90, 180, 270]:
            if angle == 0:
                rotated_crop = crop
            elif angle == 90:
                rotated_crop = np.rot90(crop, k=1)
            elif angle == 180:
                rotated_crop = np.rot90(crop, k=2)
            elif angle == 270:
                rotated_crop = np.rot90(crop, k=3)
                
            results = reader.readtext(rotated_crop, detail=0)
            print(f"Angle {angle} OCR results: {results}")
            for text_line in results:
                words = [w.upper() for w in re.sub(r'[^A-Za-z]', ' ', text_line).split() if len(w) >= 3]
                stamp_words.extend(words)
        print(f"Extracted stamp words: {set(stamp_words)}")

analyze_pdf_color_and_text("documents/G NIVETHA/INV-1781414252482.pdf", "ANANTCARS")
