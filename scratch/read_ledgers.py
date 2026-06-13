import os
import fitz
import easyocr
from pypdf import PdfReader

def extract_text_hybrid(pdf_path, reader):
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
            results = reader.readtext(png_bytes, detail=0)
            page_text = " ".join(results)
            full_ocr_text.append(page_text)
        return "\n".join(full_ocr_text).strip(), False
    except Exception as e:
        return "", False

reader = easyocr.Reader(['en'], gpu=False)
for p in [
    "documents/LANCY BABU P/LANCY LEDGER-1781348080305.pdf",
    "documents/SRaghul Selvam/LEDGER-1781345998428.pdf"
]:
    abs_p = os.path.abspath(os.path.join("c:/Users/admin/Desktop/robbinmahindra", p))
    print(f"\n====================\nFILE: {p}\n====================")
    txt, is_dig = extract_text_hybrid(abs_p, reader)
    print(f"Digital: {is_dig}, Length: {len(txt)}")
    print(txt[:2500])
