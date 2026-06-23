import fitz
import easyocr
import io
import sys
from PIL import Image, ImageEnhance
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\DISC -1781516436736.pdf"
doc = fitz.open(pdf_path)
reader = easyocr.Reader(['en'], gpu=False)

page = doc[0]
zoom = 3
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat)
png_bytes = pix.tobytes("png")
img = Image.open(io.BytesIO(png_bytes)).convert("RGB")

# Enhance contrast using PIL
enhancer = ImageEnhance.Contrast(img)
enhanced_img = enhancer.enhance(2.0)  # Increase contrast by 2.0x

# Enhance sharpness as well
sharpness = ImageEnhance.Sharpness(enhanced_img)
enhanced_img = sharpness.enhance(2.0)

img_np = np.array(enhanced_img)

print("--- Running OCR with Enhanced Contrast ---")
results = reader.readtext(img_np)
for idx, (bbox, text, conf) in enumerate(results):
    print(f"[{idx}] BBox: {bbox} | Conf: {conf:.3f} | Text: {repr(text)}")
