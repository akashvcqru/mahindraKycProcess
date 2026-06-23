import os
import fitz
import glob
from pypdf import PdfReader

def extract_text_hybrid(pdf_path):
    text = ""
    try:
        pdf_reader = PdfReader(pdf_path)
        for page in pdf_reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        text = text.strip()
    except Exception as e:
        pass
    if text:
        return text, True
        
    try:
        doc = fitz.open(pdf_path)
        full_ocr_text = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")
            import easyocr
            reader = easyocr.Reader(['en'], gpu=False)
            results = reader.readtext(png_bytes, detail=0)
            page_text = " ".join(results)
            full_ocr_text.append(page_text)
        return "\n".join(full_ocr_text).strip(), False
    except Exception as e:
        return "", False

pdf_files = glob.glob("documents/**/*.pdf", recursive=True)
for p in pdf_files:
    filename = os.path.basename(p).upper()
    if "DIS" in filename or "DISCLAIMER" in filename:
        print(f"\n====================\nFILE: {p}\n====================")
        txt, is_dig = extract_text_hybrid(p)
        print(f"Digital: {is_dig}")
        print(txt)
