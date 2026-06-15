import os
import sys
import fitz
import easyocr
import re
from pypdf import PdfReader

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def extract_text_hybrid(pdf_path):
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        text = text.strip()
    except Exception:
        pass
        
    if text:
        return text, True
        
    try:
        doc = fitz.open(pdf_path)
        full_ocr_text = []
        reader_ocr = easyocr.Reader(['en'], gpu=False)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")
            results = reader_ocr.readtext(png_bytes, detail=0)
            page_text = " ".join(results)
            full_ocr_text.append(page_text)
        return "\n".join(full_ocr_text).strip(), False
    except Exception as e:
        return f"Error: {e}", False

pdf_path = "documents/LANCY BABU P/LANCY LEDGER-1781348080305.pdf"
print("Running OCR on Lancy Ledger...")
text, is_digital = extract_text_hybrid(pdf_path)
print(f"Is Digital: {is_digital}")
print("--- Text ---")
print(text)
print("--- End ---")
