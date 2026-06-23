import os
import sys
import glob
import fitz # PyMuPDF
import easyocr
from pypdf import PdfReader
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def extract_text_hybrid(pdf_path, reader):
    print(f"\nProcessing: {os.path.basename(pdf_path)}")
    text = ""
    try:
        pdf_reader = PdfReader(pdf_path)
        for page in pdf_reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        text = text.strip()
    except Exception as e:
        print(f"Digital read error: {e}")
        
    if text:
        print("--> Extracted DIGITAL Text.")
        return text, True
        
    print("--> Running OCR via EasyOCR...")
    try:
        doc = fitz.open(pdf_path)
        full_ocr_text = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")
            
            results = reader.readtext(png_bytes, detail=0)
            page_text = " ".join(results)
            full_ocr_text.append(page_text)
            print(f"Page {page_num+1} OCR Text Sample: {page_text[:200]}...")
            
        return "\n".join(full_ocr_text).strip(), False
    except Exception as e:
        print(f"OCR failed: {e}")
        return "", False

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    documents_dir = os.path.abspath(os.path.join(script_dir, "..", "documents"))
    
    pdf_files = glob.glob(os.path.join(documents_dir, "**", "*.pdf"), recursive=True)
    if not pdf_files:
        print("No PDF files found.")
        return
        
    reader = easyocr.Reader(['en'], gpu=False)
    
    results_map = {}
    for path in pdf_files:
        text, is_digital = extract_text_hybrid(path, reader)
        rel_path = os.path.relpath(path, documents_dir)
        results_map[rel_path] = {
            "is_digital": is_digital,
            "text": text
        }
        
    out_path = os.path.join(script_dir, "extracted_texts.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results_map, f, indent=2, ensure_ascii=False)
    print(f"\nSaved all results to {out_path}")

if __name__ == "__main__":
    main()
