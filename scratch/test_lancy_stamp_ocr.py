import cv2
import fitz
import easyocr
import re
from rapidfuzz import fuzz
import numpy as np

def verify_ledger_stamp_and_signature(pdf_path, company_name):
    print("Checking stamp and signature in Ledger document...")
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=300)
        
        img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        lower_blue = np.array([90, 50, 50])
        upper_blue = np.array([130, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        
        blue_pixels = np.sum(mask > 0)
        print(f"  Blue pixels count in stamp area: {blue_pixels}")
        
        if blue_pixels < 500:
            return False, "FAIL (No blue/purple stamp or signature ink detected)"
            
        pts = np.argwhere(mask > 0)
        ymin, xmin = pts.min(axis=0)
        ymax, xmax = pts.max(axis=0)
        
        h, w, _ = img.shape
        ymin = max(0, ymin - 10)
        ymax = min(h, ymax + 10)
        xmin = max(0, xmin - 10)
        xmax = min(w, xmax + 10)
        
        crop = img[ymin:ymax, xmin:xmax]
        
        reader = easyocr.Reader(['en'], gpu=False)
        stamp_words = []
        for angle in [0, 90, 180, 270]:
            if angle == 0:
                rotated_crop = crop
            elif angle == 90:
                rotated_crop = np.rot90(crop, k=1)
            elif angle == 180:
                rotated_crop = np.rot90(crop, k=2)
            elif angle == 270:
                rotated_crop = np.rot90(crop, k=3)
                
            results = reader.readtext(rotated_crop, detail=0)
            for text_line in results:
                words = [w.upper() for w in re.sub(r'[^A-Za-z]', ' ', text_line).split() if len(w) >= 3]
                stamp_words.extend(words)
                
        stamp_words_unique = list(set(stamp_words))
        print(f"  Stamp OCR extracted words: {stamp_words_unique}")
        
        if not company_name:
            return True, "GOOD (Stamp/Signature present, but no company name was extracted from disclaimer)"
            
        company_words = [w.upper() for w in re.sub(r'[^A-Za-z]', ' ', company_name).split() if len(w) >= 3]
        matched_any = False
        matching_details = []
        for c_word in company_words:
            for s_word in stamp_words_unique:
                score = fuzz.ratio(c_word, s_word)
                if score >= 75:
                    matched_any = True
                    matching_details.append(f"'{s_word}' matches company word '{c_word}' ({score:.1f}%)")
            if len(c_word) >= 6:
                for s_word in stamp_words_unique:
                    if s_word in c_word or c_word in s_word:
                        matched_any = True
                        matching_details.append(f"'{s_word}' is substring of/contains '{c_word}'")
                        
        if matched_any:
            return True, f"GOOD (Stamp/Signature present and matches company '{company_name}': {', '.join(matching_details)})"
        else:
            return False, f"FAIL (Stamp/Signature present but does not match company '{company_name}'. Extracted stamp words: {stamp_words_unique})"
            
    except Exception as stamp_err:
        return False, f"FAIL (Error checking stamp/signature: {stamp_err})"

pdf_path = "documents/LANCY BABU P/LANCY LEDGER-1781348080305.pdf"
company_name = "VEER"  # For Lancy, the dealer name on top is VEER (from the extracted text "Mahindra VEER")
res, msg = verify_ledger_stamp_and_signature(pdf_path, company_name)
print(f"Result: {res}")
print(f"Msg: {msg}")
