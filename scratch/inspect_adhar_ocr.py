import os
import sys
import fitz # PyMuPDF
import easyocr

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    adhar_path = os.path.abspath(os.path.join(script_dir, "..", "documents", "SRaghul Selvam", "ADHAR-1781345999022.pdf"))
    
    print(f"Loading EasyOCR...")
    reader = easyocr.Reader(['en'], gpu=False)
    
    print(f"Opening PDF: {adhar_path}")
    doc = fitz.open(adhar_path)
    
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        print(f"Running OCR on page {i+1}...")
        results = reader.readtext(png_bytes, detail=0)
        print(f"--- Page {i+1} OCR Text ---")
        full_text = " ".join(results)
        print(full_text)
        print("-" * 40)

if __name__ == "__main__":
    main()
