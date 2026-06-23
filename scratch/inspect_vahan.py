import fitz
import easyocr
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\LALU PRASAD RANA\VAHANSCREENSHOT-1782199033165.pdf"
print(f"File exists: {os.path.exists(pdf_path)}")
if not os.path.exists(pdf_path):
    sys.exit(1)

doc = fitz.open(pdf_path)
print(f"Number of pages: {len(doc)}")

# 1. Try digital text extraction
digital_text = ""
for i, page in enumerate(doc):
    t = page.get_text()
    if t.strip():
        digital_text += f"\n--- Page {i+1} ---\n" + t

if digital_text.strip():
    print("=== DIGITAL TEXT FOUND ===")
    print(digital_text)
else:
    print("=== NO DIGITAL TEXT, RUNNING OCR ===")
    reader = easyocr.Reader(['en'], gpu=False)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        text = " ".join(reader.readtext(png_bytes, detail=0))
        print(f"PAGE {i+1} OCR: {text}")
