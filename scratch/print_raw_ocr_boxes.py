import os
import sys
import fitz
import easyocr
import numpy as np
from PIL import Image
import io

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

pdf_path = r"C:\Users\admin\Desktop\robbinmahindra\documents\ABILASHGOWDA A\DISC -1781516436736.pdf"

print("Loading EasyOCR...")
reader = easyocr.Reader(['en'], gpu=False)

print(f"Opening PDF: {pdf_path}")
doc = fitz.open(pdf_path)
page = doc.load_page(0)
zoom = 3
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat)
png_bytes = pix.tobytes("png")
img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
img_np = np.array(img)

print("Running OCR...")
raw_results = reader.readtext(img_np)

print("\n=== RAW OCR RESULTS ===")
for i, (bbox, text, conf) in enumerate(raw_results):
    # Calculate box bounds
    x_coords = [p[0] for p in bbox]
    y_coords = [p[1] for p in bbox]
    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)
    y_center = (y_min + y_max) / 2.0
    print(f"Box {i:03d} (Conf: {conf:.4f}): '{text}' | Range: X[{x_min:.1f} - {x_max:.1f}] Y[{y_min:.1f} - {y_max:.1f}] Y_Center: {y_center:.1f}")
print("=========================")
