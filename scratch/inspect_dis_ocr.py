import os
import sys
import fitz # PyMuPDF
import easyocr

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    reader = easyocr.Reader(['en'], gpu=False)
    
    docs = [
        ("LANCY BABU P", "LANCY DISCLAIMER-1781348080456.pdf"),
        ("SRaghul Selvam", "DIS-1781345998542.pdf")
    ]
    
    for customer, file_name in docs:
        dis_path = os.path.abspath(os.path.join(script_dir, "..", "documents", customer, file_name))
        if not os.path.exists(dis_path):
            print(f"File not found: {dis_path}")
            continue
            
        print(f"\n==========================================")
        print(f"Opening PDF: {file_name}")
        print(f"==========================================")
        doc = fitz.open(dis_path)
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
