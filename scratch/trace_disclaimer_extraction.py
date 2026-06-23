import os
import sys
import logging
import fitz
import easyocr
import numpy as np
from PIL import Image
import io
from rapidfuzz import fuzz
import re

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Nested functions to avoid name clashes
def clean_label(text):
    if not text:
        return ""
    return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower().strip()

def clean_chassis(text):
    if not text or text == "NOT_FOUND":
        return "NOT_FOUND"
    cleaned = text.replace(" ", "").upper()
    cleaned = re.sub(r'^[:\-\.\;\|_]+', '', cleaned)
    return cleaned

def clean_invoice(text):
    if not text or text == "NOT_FOUND":
        return "NOT_FOUND"
    cleaned = text.replace(" ", "").upper()
    cleaned = re.sub(r'^[:\-\.\;\|_]+', '', cleaned)
    return cleaned

def clean_amount(text):
    if not text or text == "NOT_FOUND":
        return "NOT_FOUND"
    cleaned_chars = []
    char_map = {
        'o': '0', 'O': '0', 'q': '0', 'Q': '0', 'd': '0', 'D': '0',
        'i': '1', 'I': '1', 'l': '1', 't': '1', 'T': '1', 'j': '1',
        's': '5', 'S': '5', 'b': '6', 'g': '9', 'z': '2', 'Z': '2',
        'f': '0', '?' : '0', 'k': '1', 'K': '1'
    }
    for c in text:
        if c.isdigit():
            cleaned_chars.append(c)
        elif c in char_map:
            cleaned_chars.append(char_map[c])
        elif c in [',', '.', '/', '-']:
            cleaned_chars.append(c)
    cleaned_str = "".join(cleaned_chars)
    digits = "".join([c for c in cleaned_str if c.isdigit()])
    if not digits:
        return text
    val = int(digits)
    if val in [10, 15, 20, 25]:
        return str(val * 1000)
    if val in [100, 150, 200, 250]:
        return str(val * 100)
    if val in [1000, 1500, 2000, 2500]:
        return str(val * 10)
    valid_amounts = [10000, 15000, 20000, 25000]
    for amt in valid_amounts:
        if abs(val - amt) < 2000:
            return str(amt)
    return digits

def clean_date(text):
    if not text or text == "NOT_FOUND":
        return "NOT_FOUND"
    stripped = text.strip()
    if stripped.startswith('/'):
        stripped = '1' + stripped.lstrip('/')
    char_map = {
        'o': '0', 'O': '0', 'q': '0', 'Q': '0', 'd': '0', 'D': '0',
        'i': '1', 'I': '1', 'l': '1', 't': '1', 'T': '1', 'j': '1',
        's': '5', 'S': '5', 'b': '6', 'g': '9', 'z': '2', 'Z': '2',
        'f': '0', '?' : '0', 'k': '1', 'K': '1', '&': '6'
    }
    cleaned_chars = []
    for c in stripped:
        if c.isdigit() or c in ['/', '-', '.']:
            cleaned_chars.append(c)
        elif c in char_map:
            cleaned_chars.append(char_map[c])
        elif c.isspace():
            cleaned_chars.append('/')
    cleaned_str = "".join(cleaned_chars)
    cleaned_str = re.sub(r'[\-\.]', '/', cleaned_str)
    cleaned_str = re.sub(r'/+', '/', cleaned_str)
    cleaned_str = cleaned_str.strip('/')
    match = re.search(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', cleaned_str)
    if match:
        day, month, year = match.group(0).split('/')
        if len(day) == 1: day = '0' + day
        if len(month) == 1: month = '0' + month
        if len(year) == 2: year = '20' + year
        if len(year) == 3 and year.startswith('202'): year = year + '6'
        return f"{day}/{month}/{year}"
    return text.strip()

def clean_dealership(text):
    if not text or text == "NOT_FOUND":
        return "NOT_FOUND"
    return re.sub(r'^[:\-\.\;\|_]+', '', text).strip()

def is_template_text(text):
    text_lower = text.lower()
    templates = [
        "from dealership", "from the", "for buying", "engine no", 
        "invoice no", "invoice date", "customer signature", 
        "dealer authorized", "authorized person", "dealership name"
    ]
    for t in templates:
        if t in text_lower or fuzz.token_sort_ratio(clean_label(text), clean_label(t)) > 80:
            return True
    return False

def is_placeholder_value(text):
    text_clean = text.lower().strip()
    placeholders = [
        "ddmmyyyy", "ddimmiyyyy", "ddmmyy", "dd/mm/yyyy", "dd-mm-yyyy", 
        "dd.mm.yyyy", "yyyy", "mm", "dd", "ddimmiyyyy", "ddmmiyyyy"
    ]
    if text_clean in placeholders:
        return True
    return False

def get_value_from_remainder(remainder):
    tokens = remainder.split()
    value_tokens = []
    for tok in tokens:
        if is_template_text(tok) or tok.lower() in ["from", "for", "the", "buying", "of", "new", "with", "as"]:
            break
        value_tokens.append(tok)
    return " ".join(value_tokens).strip()

def parse_easyocr_box(box_raw):
    box = []
    for pt in box_raw:
        box.append([float(pt[0]), float(pt[1])])
    x_coords = [p[0] for p in box]
    y_coords = [p[1] for p in box]
    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)
    y_center = (y_min + y_max) / 2.0
    return {
        'box': box,
        'x_min': x_min,
        'x_max': x_max,
        'y_min': y_min,
        'y_max': y_max,
        'y_center': y_center
    }

pdf_path = r"C:\Users\admin\Desktop\robbinmahindra\documents\ABILASHGOWDA A\DISC -1781516436736.pdf"
customer_name = "ABILASHGOWDA A"

spatial_patterns = {
    "Customer Name": ["name of customer", "name of customer:", "name & signature", "customer signature"],
    "Registration No": ["registration number", "registration no", "reg no", "registration number:"],
    "Vehicle Make": ["vehicle make", "make", "vehicle make:"],
    "Vehicle Model": ["vehicle model", "model", "vehicle model:"],
    "New Vehicle Model": ["new vehicle model", "vehicle model:", "buying new vehicle model", "for buying new vehicle model"],
    "Chassis No": ["chassis no", "chassis number", "chassis no:"],
    "Invoice No": ["invoice no", "invoice number", "invoice no:"],
    "Invoice Date": ["invoice date", "invoice date:", "date:", "date dd/mm/yyyy", "date ddimmiyyyy"],
    "Welcome Bonus Amount": [
        "welcome bonus scheme of rs", 
        "bonus of rs", 
        "welcome bonus", 
        "bonus scheme of rs", 
        "bonus of rs:",
        "have availed welcome bonus of rs"
    ]
}

print("Loading EasyOCR...")
reader = easyocr.Reader(['en'], gpu=False)

print("Opening PDF...")
doc = fitz.open(pdf_path)
page = doc.load_page(0)
zoom = 3
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat)
png_bytes = pix.tobytes("png")
img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
img_np = np.array(img)

raw_results = reader.readtext(img_np)
ocr_items = []
for bbox, text, conf in raw_results:
    if conf < 0.05:
        continue
    parsed = parse_easyocr_box(bbox)
    parsed['text'] = text.strip()
    parsed['conf'] = conf
    ocr_items.append(parsed)

used_boxes = set()
fields_order = [
    "Chassis No", "Invoice No", "Vehicle Make", "Vehicle Model", 
    "New Vehicle Model", "Customer Name", "Registration No", 
    "Invoice Date", "Welcome Bonus Amount"
]

print("\n--- TRACING SPATIAL MATCHING ---")
for field in fields_order:
    print(f"\n>> Field: {field}")
    patterns = spatial_patterns[field]
    extracted_val = "NOT_FOUND"
    matched_idx = -1
    
    # 1. Inline extraction
    for idx, item in enumerate(ocr_items):
        if idx in used_boxes or item['conf'] < 0.4:
            continue
        text = item['text']
        cleaned = clean_label(text)
        for pat in patterns:
            clean_pat = clean_label(pat)
            if clean_pat in cleaned:
                match = re.search(re.escape(pat), text, re.IGNORECASE)
                if match:
                    idx_end = match.end()
                    remainder = text[idx_end:].strip()
                    remainder = re.sub(r'^[:\s\-\.\;\|_]+', '', remainder).strip()
                    if field == "Welcome Bonus Amount":
                        remainder = re.sub(r'^(?:of|rs|rs\.|rs\:|rupees|rupees\.)\s*', '', remainder, flags=re.IGNORECASE).strip()
                    inline_val = get_value_from_remainder(remainder)
                    print(f"  [Inline Trial] Box {idx} '{text}' matches pattern '{pat}' -> remainder: '{remainder}' -> val: '{inline_val}'")
                    if len(inline_val) >= 2 and not is_placeholder_value(inline_val):
                        extracted_val = inline_val
                        matched_idx = idx
                        used_boxes.add(idx)
                        break
        if matched_idx != -1:
            break
            
    # 2. Spatial extraction
    if extracted_val == "NOT_FOUND":
        best_label_item = None
        best_idx = -1
        best_score = 0
        for idx, item in enumerate(ocr_items):
            if idx in used_boxes or item['conf'] < 0.4:
                continue
            text = item['text']
            for pat in patterns:
                score = fuzz.token_sort_ratio(clean_label(text), clean_label(pat))
                if score > best_score:
                    best_score = score
                    best_label_item = item
                    best_idx = idx
                    
        if best_label_item and best_score > 70:
            print(f"  [Label Found] Box {best_idx} '{best_label_item['text']}' matches pattern (Score: {best_score})")
            label_x_max = best_label_item['x_max']
            label_x_min = best_label_item['x_min']
            label_y_center = best_label_item['y_center']
            
            candidates = []
            for idx, item in enumerate(ocr_items):
                if idx == best_idx or idx in used_boxes:
                    continue
                if item['conf'] < 0.15:
                    continue
                if item['x_min'] > label_x_min + 10:
                    y_diff = abs(item['y_center'] - label_y_center)
                    if y_diff < 20:
                        candidates.append((idx, item))
                        
            if candidates:
                candidates.sort(key=lambda x: x[1]['x_min'])
                print(f"  [Candidates] {[ (c[0], c[1]['text'], c[1]['conf'], c[1]['x_min'] - label_x_max) for c in candidates ]}")
                value_parts = []
                prev_x_max = label_x_max
                for idx, cand in candidates:
                    gap = cand['x_min'] - prev_x_max
                    max_allowed_gap = 200 if len(value_parts) == 0 else 120
                    print(f"    Checking cand Box {idx} '{cand['text']}' (Conf: {cand['conf']:.4f}) | gap: {gap:.1f} (max: {max_allowed_gap})")
                    if gap < max_allowed_gap:
                        if cand['conf'] < 0.4 and gap >= 120:
                            print(f"      Rejected: conf < 0.4 ({cand['conf']:.4f}) and gap >= 120 ({gap:.1f})")
                            break
                        if not is_template_text(cand['text']):
                            value_parts.append(cand['text'])
                            used_boxes.add(idx)
                            prev_x_max = cand['x_max']
                            print(f"      Appended! Next prev_x_max: {prev_x_max:.1f}")
                        else:
                            print(f"      Rejected: is template text")
                    else:
                        print(f"      Rejected: gap ({gap:.1f}) >= max ({max_allowed_gap})")
                        break
                        
                if value_parts:
                    extracted_val = " ".join(value_parts).strip()
                    used_boxes.add(best_idx)
                    print(f"  [Spatial Found] Value: '{extracted_val}'")
            else:
                print("  [Spatial Search] No horizontal candidates found.")
        else:
            print(f"  [Label Search] No label matching patterns found (best score: {best_score}).")

    print(f"  --> Extracted Raw: '{extracted_val}'")
