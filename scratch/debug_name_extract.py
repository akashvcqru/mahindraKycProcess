import sys
import os
import re
import fitz
from PIL import Image
import io
import numpy as np
import easyocr

file_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\HARISH M B\DISC-1781972859901.pdf"
reader = easyocr.Reader(['en'], gpu=False)
doc = fitz.open(file_path)

for page in doc:
    zoom = 3
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    png_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    img_np = np.array(img)
    
    raw_results = reader.readtext(img_np)
    
    ocr_items = []
    for bbox, text, conf in raw_results:
        if conf < 0.01:
            continue
        box = []
        for pt in bbox:
            box.append([float(pt[0]), float(pt[1])])
        x_coords = [p[0] for p in box]
        y_coords = [p[1] for p in box]
        x_min = min(x_coords)
        x_max = max(x_coords)
        y_min = min(y_coords)
        y_max = max(y_coords)
        y_center = (y_min + y_max) / 2.0
        
        ocr_items.append({
            'text': text.strip(),
            'conf': conf,
            'x_min': x_min,
            'x_max': x_max,
            'y_center': y_center
        })
        
    print("OCR items around y_center = 1994:")
    for idx, item in enumerate(ocr_items):
        if 1950 <= item['y_center'] <= 2040:
            print(f"[{idx}] '{item['text']}' (Conf: {item['conf']:.2f}) x_min={item['x_min']:.1f} x_max={item['x_max']:.1f} y_center={item['y_center']:.1f}")
