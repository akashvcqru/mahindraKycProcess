import os
import sys
import glob
import fitz # PyMuPDF
import easyocr
from pypdf import PdfReader
from PIL import Image
import io

# Avoid charmap codec errors on Windows when printing Unicode/block characters
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def extract_text_hybrid(pdf_path):
    print(f"\nProcessing: {os.path.basename(pdf_path)}")
    
    # Step 1: Try digital PDF text extraction
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        text = text.strip()
    except Exception as e:
        print(f"Digital read error: {e}")
        
    if text:
        print("--> Extracted DIGITAL Text successfully.")
        return text
        
    # Step 2: If no text, run OCR
    print("--> No digital text. Running OCR via PyMuPDF + EasyOCR...")
    try:
        doc = fitz.open(pdf_path)
        full_ocr_text = []
        
        # Initialize EasyOCR reader (only English 'en' needed)
        reader = easyocr.Reader(['en'], gpu=False) # CPU inference
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Render page to PNG bytes (150 DPI is good for OCR balance)
            pix = page.get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")
            
            # Run OCR on the image bytes
            results = reader.readtext(png_bytes, detail=0)
            page_text = " ".join(results)
            full_ocr_text.append(page_text)
            print(f"Page {page_num+1} OCR Text Sample: {page_text[:300]}...")
            
        return "\n".join(full_ocr_text).strip()
    except Exception as e:
        print(f"OCR failed: {e}")
        return ""

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    documents_dir = os.path.abspath(os.path.join(script_dir, "..", "documents"))
    
    # Let's test a few specific PDFs (digital and scanned)
    pdf_files = glob.glob(os.path.join(documents_dir, "**", "*.pdf"), recursive=True)
    if not pdf_files:
        print("No PDF files found.")
        return
        
    for path in pdf_files[:3]: # test first 3 files
        text = extract_text_hybrid(path)
        print(f"Extracted Text Length: {len(text)}")
        if text:
            # Let's check for PAN-like or Certificate-like strings
            import re
            pan_match = re.search(r'[A-Z]{5}[0-9]{4}[A-Z]', text)
            if pan_match:
                print(f"FOUND PAN: {pan_match.group(0)}")
            dob_match = re.search(r'\b\d{2}[-/\.]\d{2}[-/\.]\d{4}\b', text)
            if dob_match:
                print(f"FOUND DOB: {dob_match.group(0)}")

if __name__ == "__main__":
    main()
