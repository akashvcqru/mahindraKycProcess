import fitz
import easyocr
import io
import sys
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\LANCY BABU P\LANCY DISCLAIMER-1781348080456.pdf"
doc = fitz.open(pdf_path)
reader = easyocr.Reader(['en'], gpu=False)

for i, page in enumerate(doc):
    # Render at 3x zoom (216 DPI)
    zoom = 3
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    png_bytes = pix.tobytes("png")
    
    print(f"--- Page {i+1} EasyOCR (with boxes) ---")
    results = reader.readtext(png_bytes)
    for idx, (bbox, text, conf) in enumerate(results):
        print(f"[{idx}] BBox: {bbox} | Conf: {conf:.3f} | Text: {repr(text)}")
