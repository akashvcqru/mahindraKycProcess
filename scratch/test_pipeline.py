import os
import sys
import re
import fitz # PyMuPDF
from pypdf import PdfReader
from rapidfuzz import fuzz

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

_ocr_reader = None

def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        print("Initializing EasyOCR reader...")
        import easyocr
        _ocr_reader = easyocr.Reader(['en'], gpu=False)
    return _ocr_reader

def extract_text_hybrid(pdf_path):
    print(f"Reading: {os.path.basename(pdf_path)}...")
    text = ""
    try:
        pdf_reader = PdfReader(pdf_path)
        for page in pdf_reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        text = text.strip()
    except Exception as e:
        print(f"  Digital read error: {e}")
        
    if text:
        return text, True
        
    print("  Scanned document. Running OCR...")
    try:
        reader = get_ocr_reader()
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
        print(f"  OCR failed: {e}")
        return "", False

def extract_best_name(text, claim_name):
    cleaned_text = re.sub(r'[^A-Za-z\s]', ' ', text)
    words = [w for w in cleaned_text.split() if len(w) > 0]
    
    claim_words = [w for w in re.sub(r'[^A-Za-z\s]', ' ', claim_name).split() if len(w) > 0]
    n = len(claim_words)
    if n == 0:
        return "", 0.0
        
    best_name = ""
    best_score = 0.0
    
    for size in [n, n+1, n+2]:
        for i in range(len(words) - size + 1):
            window_words = words[i:i+size]
            candidate = " ".join(window_words)
            score = fuzz.token_sort_ratio(candidate.lower(), claim_name.lower())
            if score > best_score:
                best_score = score
                best_name = candidate
                
    return best_name, best_score

def classify_and_extract(file_path, text, claim_customer_name):
    filename = os.path.basename(file_path).upper()
    text_upper = text.upper()
    
    is_pan = "PAN" in filename
    is_cod = "COD" in filename or "DISCLAIMER" in filename or "DIS" in filename
    
    # Fallback to text content checks if filename is ambiguous
    if not is_pan and not is_cod:
        if "PERMANENT ACCOUNT NUMBER" in text_upper or "INCOME TAX DEPARTMENT" in text_upper:
            is_pan = True
        elif "CERTIFICATE OF DESTRUCTION" in text_upper or "CERTIFICATE OF DEPOSIT" in text_upper or "DISCLAIMER FOR" in text_upper:
            is_cod = True
            
    result = {
        "file_name": os.path.basename(file_path),
        "file_type": "UNKNOWN",
        "extracted_data": {},
        "validations": {}
    }
    
    if is_pan:
        result["file_type"] = "PAN"
        # Extract PAN No
        pan_match = re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', text, re.IGNORECASE)
        pan_no = pan_match.group(0).upper() if pan_match else None
        
        # Extract DOB
        dob_match = re.search(r'\b\d{2}[-/\.]\d{2}[-/\.]\d{4}\b', text)
        dob = dob_match.group(0) if dob_match else None
        
        # Extract Name using sliding window
        extracted_name, name_score = extract_best_name(text, claim_customer_name)
        
        result["extracted_data"] = {
            "PAN Number": pan_no,
            "DOB": dob,
            "Name": extracted_name
        }
        result["validations"] = {
            "Name Match Score": name_score,
            "Name Match Status": "MATCH" if name_score >= 80 else "MISMATCH",
            "PAN Status": "FOUND" if pan_no else "NOT FOUND",
            "DOB Status": "FOUND" if dob else "NOT FOUND"
        }
        
    elif is_cod:
        result["file_type"] = "COD"
        # Extract Certificate No
        cod_match = re.search(r'\b(COD[A-Z0-9]+)\b', text, re.IGNORECASE)
        cert_no = cod_match.group(0) if cod_match else None
        if not cert_no:
            fallback_match = re.search(r'Deposit\s*\(?coD\)?,\s*with\s*number\s*-\s*([A-Z0-9]+)', text, re.IGNORECASE)
            if fallback_match:
                cert_no = fallback_match.group(1)
                
        # Extract User Name using sliding window
        extracted_name, name_score = extract_best_name(text, claim_customer_name)
        
        result["extracted_data"] = {
            "Certificate No": cert_no,
            "User Name": extracted_name
        }
        result["validations"] = {
            "Name Match Score": name_score,
            "Name Match Status": "MATCH" if name_score >= 80 else "MISMATCH",
            "Certificate Status": "FOUND" if cert_no else "NOT FOUND"
        }
        
    return result

def run_pipeline_for_customer(customer_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    customer_dir = os.path.join(script_dir, "..", "documents", customer_name)
    customer_dir = os.path.abspath(customer_dir)
    
    if not os.path.exists(customer_dir):
        print(f"Customer directory not found: {customer_dir}")
        return
        
    print(f"\n==================================================")
    print(f"RUNNING PIPELINE FOR CUSTOMER: {customer_name}")
    print(f"==================================================")
    
    import glob
    pdf_files = glob.glob(os.path.join(customer_dir, "*.pdf"))
    
    for pdf_path in pdf_files:
        text, is_digital = extract_text_hybrid(pdf_path)
        res = classify_and_extract(pdf_path, text, customer_name)
        
        print(f"\nFile: {res['file_name']} (Type: {res['file_type']})")
        print(f"  Extracted Data: {res['extracted_data']}")
        print(f"  Validations: {res['validations']}")

if __name__ == "__main__":
    run_pipeline_for_customer("LANCY BABU P")
    run_pipeline_for_customer("SRaghul Selvam")
