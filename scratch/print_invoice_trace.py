import os
import sys
import numpy as np
from PIL import Image
import io
import easyocr
import fitz
from rapidfuzz import fuzz
import re

# We will reproduce the extract_disclaimer_spatial logic and print trace logs.
file_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\ABILASHGOWDA A\DISC -1781516436736.pdf"

def clean_label(text):
    if not text:
        return ""
    return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower().strip()

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
    x_min = min(x_coords)
    x_max = max(x_coords)
    y_min = min(y_coords)
    y_max = max(y_coords)
    y_center = (y_min + y_max) / 2.0
    return {
        'box': box,
        'x_min': x_min,
        'x_max': x_max,
        'y_min': y_min,
        'y_max': y_max,
        'y_center': y_center
    }

spatial_patterns = {
    "Customer Name": ["name of customer", "name of customer:", "name & signature", "customer signature"],
    "Registration No": ["registration number", "registration no", "reg no", "registration number:"],
    "Vehicle Make": ["vehicle make", "make", "vehicle make:", "dealership name", "dealership name:", "dealership name_"],
    "Vehicle Model": ["vehicle model", "model", "vehicle model:"],
    "New Vehicle Model": ["new vehicle model", "vehicle model:", "buying new vehicle model", "for buying new vehicle model"],
    "Chassis No": ["chassis no", "chassis number", "chassis no:"],
    "Invoice No": ["invoice no", "invoice number", "invoice no:", "rvoice", "rvoice no", "#rvoice", "#rvoice _ no"],
    "Invoice Date": ["invoice date", "invoice date:", "date:"],
    "Welcome Bonus Amount": [
        "welcome bonus scheme of rs", 
        "bonus of rs", 
        "welcome bonus", 
        "bonus scheme of rs", 
        "bonus of rs:",
        "have availed welcome bonus of rs"
    ]
}

reader = easyocr.Reader(['en'], gpu=False)
doc = fitz.open(file_path)
page = doc[0]

zoom = 3
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat)
png_bytes = pix.tobytes("png")
img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
img_np = np.array(img)

raw_results = reader.readtext(img_np)
ocr_items = []
for bbox, text, conf in raw_results:
    if conf < 0.01:
        continue
    parsed = parse_easyocr_box(bbox)
    parsed['text'] = text.strip()
    parsed['conf'] = conf
    ocr_items.append(parsed)

used_boxes = set()
fields_order = [
    "Customer Name", "Registration No", "Chassis No", "New Vehicle Model",
    "Vehicle Make", "Vehicle Model", "Invoice No", "Invoice Date", 
    "Welcome Bonus Amount"
]

for field in fields_order:
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
            label_x_max = best_label_item['x_max']
            label_x_min = best_label_item['x_min']
            label_y_center = best_label_item['y_center']
            
            candidates = []
            for idx, item in enumerate(ocr_items):
                if idx == best_idx or idx in used_boxes:
                    continue
                gap = item['x_min'] - label_x_max
                req_conf = 0.01 if gap < 120 else 0.15
                if item['conf'] < req_conf:
                    continue
                if item['x_min'] > label_x_max - 20:
                    y_diff = abs(item['y_center'] - label_y_center)
                    if y_diff < 35:
                        candidates.append((idx, item))
                        
            print(f"\n[{field}] Label matched: '{best_label_item['text']}' (idx {best_idx}) | used_boxes status before: {used_boxes}")
            if candidates:
                candidates.sort(key=lambda x: x[1]['x_min'])
                value_parts = []
                prev_x_max = label_x_max
                for idx, cand in candidates:
                    gap = cand['x_min'] - prev_x_max
                    max_allowed_gap = 200 if len(value_parts) == 0 else 120
                    if gap < max_allowed_gap:
                        if cand['conf'] < 0.4 and gap >= 120:
                            print(f"  cand '{cand['text']}' (idx {idx}) rejected: conf < 0.4 and gap >= 120")
                            break
                        cand_lower = cand['text'].lower()
                        stop_kws = ["have", "availed", "welcome", "bonus", "scheme", "from", "for", "buying", "new", "vehicle", "model", "chassis", "engine", "invoice", "date", "customer", "signature"]
                        active_patterns_words = []
                        for pat in patterns:
                            active_patterns_words.extend(clean_label(pat).split())
                        filtered_stop_kws = [kw for kw in stop_kws if kw not in active_patterns_words]
                        
                        if any(kw in cand_lower for kw in filtered_stop_kws):
                            print(f"  cand '{cand['text']}' (idx {idx}) rejected: hit stop keyword")
                            break

                        if not is_template_text(cand['text']):
                            value_parts.append(cand['text'])
                            used_boxes.add(idx)
                            prev_x_max = cand['x_max']
                            print(f"  cand '{cand['text']}' (idx {idx}) appended! used_boxes now: {used_boxes}")
                        else:
                            print(f"  cand '{cand['text']}' (idx {idx}) rejected: is template text")
                    else:
                        print(f"  cand '{cand['text']}' (idx {idx}) rejected: gap {gap} >= max_allowed_gap {max_allowed_gap}")
                        break
                if value_parts:
                    extracted_val = " ".join(value_parts).strip()
                    used_boxes.add(best_idx)
            else:
                print(f"  No candidates found for field {field}")
    print(f"--> Extracted raw value for {field}: '{extracted_val}'")
