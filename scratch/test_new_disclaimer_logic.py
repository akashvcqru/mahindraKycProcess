import os
import glob
import fitz
import easyocr

reader = easyocr.Reader(['en'], gpu=False)

def extract_ocr_text(pdf_path):
    doc = fitz.open(pdf_path)
    full_ocr_text = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        results = reader.readtext(png_bytes, detail=0)
        page_text = " ".join(results)
        full_ocr_text.append(page_text)
    return "\n".join(full_ocr_text).strip()

def validate_disclaimer(text, filename):
    text_norm = text.upper()
    
    old_keywords = ["SOLEMNLY", "AFFIRM", "DECLARE", "HEREBY SOLEMNLY", "AFFIRM AND DECLARE"]
    has_old_format = any(kw in text_norm for kw in old_keywords)
    
    new_keywords = [
        "CUSTOMER DISCLAIMER",
        "CONFIRM",
        "WELCOME" if "WELCOME" in text_norm else "WELCOMC",
        "DEALER" if "DEALER" in text_norm else "DEATER",
        "VEHICLE" if "VEHICLE" in text_norm else "VEHIC",
        "CHASSIS" if "CHASSIS" in text_norm else "GHASSIS",
        "ENGINE" if "ENGINE" in text_norm else "ENGIN",
        "INVOICE"
    ]
    matching_new_kws = sum(1 for kw in new_keywords if kw in text_norm)
    
    print(f"File: {filename}")
    print(f"  - Matches old: {has_old_format}")
    print(f"  - New keywords count: {matching_new_kws}/8")
    
    if has_old_format or matching_new_kws < 5:
        print("  - STATUS: HOLD (Format mismatch)")
        return False
    else:
        print("  - STATUS: PASS")
        return True

print("--- Testing current disclaimers using OCR ---")
pdf_files = glob.glob("documents/**/*.pdf", recursive=True)
for p in pdf_files:
    filename = os.path.basename(p).upper()
    if "DIS" in filename or "DISCLAIMER" in filename:
        txt = extract_ocr_text(p)
        validate_disclaimer(txt, filename)
