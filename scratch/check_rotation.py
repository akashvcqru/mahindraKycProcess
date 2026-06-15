import fitz
import easyocr
import io
import sys
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\DISC -1781516436736.pdf"
doc = fitz.open(pdf_path)
reader = easyocr.Reader(['en'], gpu=False)

page = doc[0]
zoom = 3
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat)
png_bytes = pix.tobytes("png")
img = Image.open(io.BytesIO(png_bytes))

target_keywords = ["disclaimer", "chassis", "invoice", "dealership", "welcome", "bonus"]

for angle in [0, 90, 180, 270]:
    if angle == 0:
        rotated_img = img
    else:
        rotated_img = img.rotate(-angle, expand=True)
        
    img_byte_arr = io.BytesIO()
    rotated_img.save(img_byte_arr, format='PNG')
    rotated_bytes = img_byte_arr.getvalue()
    
    results = reader.readtext(rotated_bytes, detail=0)
    text_candidate = " ".join(results).lower()
    
    score = sum(1 for kw in target_keywords if kw in text_candidate)
    print(f"Angle {angle}° -> Score: {score}")
    print(f"Sample: {text_candidate[:300]}")
    print("-" * 50)
