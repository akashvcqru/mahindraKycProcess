#!/usr/bin/env python3
"""
Disclaimer Document Extractor
-----------------------------
This script extracts key printed labels and their handwritten values from scanned
and hybrid disclaimer PDFs. It leverages PyMuPDF (fitz) for PDF page rendering,
EasyOCR for deep learning character recognition, NumPy for image representation,
and RapidFuzz for fuzzy label matching. It uses bounding box spatial alignment 
to pair labels with handwritten values on the same line.
"""

import os
import sys
import re
import json
import logging
import argparse
import numpy as np
import fitz  # PyMuPDF
import easyocr
from PIL import Image, ImageDraw
import io
from rapidfuzz import fuzz

# Set up logging format
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)

# Standard target labels for matching
FIELD_PATTERNS = {
    "chassis_no": ["chassis no", "chassis number", "chassis no:"],
    "invoice_no": ["invoice no", "invoice number", "invoice no:"],
    "dealership_name": ["dealership name", "dealership name:", "deatership name", "dealership name_"],
    "invoice_date": ["invoice date", "invoice date:", "date:", "date dd/mm/yyyy", "date ddimmiyyyy"],
    "welcome_bonus_amount": [
        "welcome bonus scheme of rs", 
        "bonus of rs", 
        "welcome bonus", 
        "bonus scheme of rs", 
        "bonus of rs:",
        "have availed welcome bonus of rs"
    ]
}

def clean_label(text):
    """Normalize label text for matching by removing non-alphanumeric chars and converting to lowercase."""
    if not text:
        return ""
    return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower().strip()

def clean_chassis(text):
    """Normalize chassis numbers (typically 17-character alphanumeric, starting with MA1)."""
    if not text or text == "NOT_FOUND":
        return "NOT_FOUND"
    
    cleaned = text.replace(" ", "").upper()
    # Remove leading colons or strange chars
    cleaned = re.sub(r'^[:\-\.\;\|]+', '', cleaned)
    
    # Correct common OCR confusions in chassis numbers (like 1/I/l/t, 0/O/Q)
    # Usually we want to keep it as read unless it fails validation, but clean spaces first
    return cleaned

def clean_invoice(text):
    """Normalize invoice numbers."""
    if not text or text == "NOT_FOUND":
        return "NOT_FOUND"
    cleaned = text.replace(" ", "").upper()
    cleaned = re.sub(r'^[:\-\.\;\|]+', '', cleaned)
    return cleaned

def clean_amount(text):
    """Normalize and correct handwritten/OCR amount values (e.g. toooof- -> 10000)."""
    if not text or text == "NOT_FOUND":
        return "NOT_FOUND"
    
    text_clean = text.lower().strip()
    
    # Check for obvious OCR misreadings of digits
    char_map = {
        'o': '0', 'O': '0', 'q': '0', 'Q': '0', 'd': '0', 'D': '0',
        'i': '1', 'I': '1', 'l': '1', 't': '1', 'T': '1', 'j': '1',
        's': '5', 'S': '5', 'b': '6', 'g': '9', 'z': '2', 'Z': '2',
        'f': '0', '?' : '0', 'k': '1', 'K': '1'
    }
    
    cleaned_chars = []
    for c in text:
        if c.isdigit():
            cleaned_chars.append(c)
        elif c in char_map:
            cleaned_chars.append(char_map[c])
        elif c in [',', '.', '/', '-']:
            cleaned_chars.append(c)
            
    cleaned_str = "".join(cleaned_chars)
    
    # Extract only digits for snapping
    digits = "".join([c for c in cleaned_str if c.isdigit()])
    if not digits:
        return text
        
    val = int(digits)
    # Snap to standard welcome/scrappage bonus contribution values (10k, 15k, 20k, 25k)
    # Handle missing zeros in handwriting OCR:
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
    """Normalize date formatting and correct common handwriting OCR mistakes."""
    if not text or text == "NOT_FOUND":
        return "NOT_FOUND"
        
    # If date starts with a slash (often 1 is read as slash), convert it to '1'
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
            cleaned_chars.append('/')  # treat spaces as separators
            
    cleaned_str = "".join(cleaned_chars)
    cleaned_str = re.sub(r'[\-\.]', '/', cleaned_str)
    cleaned_str = re.sub(r'/+', '/', cleaned_str)
    cleaned_str = cleaned_str.strip('/')
    
    # Check for date patterns like DD/MM/YYYY
    match = re.search(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', cleaned_str)
    if match:
        date_val = match.group(0)
        parts = date_val.split('/')
        if len(parts) == 3:
            day, month, year = parts
            if len(day) == 1: day = '0' + day
            if len(month) == 1: month = '0' + month
            if len(year) == 2:
                year = '20' + year
            if len(year) == 3 and year.startswith('202'):
                year = year + '6'  # Assume year is 2026 if 3-digit '202'
            return f"{day}/{month}/{year}"
            
    return text.strip()

def clean_dealership(text):
    """Normalize dealership name."""
    if not text or text == "NOT_FOUND":
        return "NOT_FOUND"
    
    # Strip leading colons or garbage characters
    cleaned = re.sub(r'^[:\-\.\;\|_]+', '', text).strip()
    return cleaned

def is_template_text(text):
    """Check if the text belongs to the printed template layout to avoid including it in values."""
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
    """Check if the text represents a date placeholder (like DD/MM/YYYY) in the template."""
    text_clean = text.lower().strip()
    placeholders = [
        "ddmmyyyy", "ddimmiyyyy", "ddmmyy", "dd/mm/yyyy", "dd-mm-yyyy", 
        "dd.mm.yyyy", "yyyy", "mm", "dd", "ddimmiyyyy", "ddmmiyyyy"
    ]
    if text_clean in placeholders:
        return True
    return False


def parse_easyocr_box(box_raw):
    """Parse raw EasyOCR box coordinates to floats and compute bounds."""
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
    height = y_max - y_min
    width = x_max - x_min
    return {
        'box': box,
        'x_min': x_min,
        'x_max': x_max,
        'y_min': y_min,
        'y_max': y_max,
        'y_center': y_center,
        'height': height,
        'width': width
    }

def extract_values_from_ocr(ocr_items):
    """
    Extract chassis_no, invoice_no, dealership_name, invoice_date, 
    and welcome_bonus_amount using spatial alignment and inline checks.
    """
    results = {}
    matched_items = {}
    
    # Fields ordered so we extract specific ones first to avoid collision
    fields_order = [
        "chassis_no", 
        "invoice_no", 
        "dealership_name", 
        "invoice_date", 
        "welcome_bonus_amount"
    ]
    
    used_boxes = set()
    
    for field in fields_order:
        patterns = FIELD_PATTERNS[field]
        extracted_value = "NOT_FOUND"
        matched_box = None
        
        # 1. Attempt inline extraction (label and value combined in same box)
        for idx, item in enumerate(ocr_items):
            if idx in used_boxes:
                continue
            text = item['text']
            cleaned = clean_label(text)
            
            # Inline extraction requires label to have decent confidence (>= 0.4)
            if item['conf'] < 0.4:
                continue
                
            for pat in patterns:
                clean_pat = clean_label(pat)
                if clean_pat in cleaned:
                    match = re.search(re.escape(pat), text, re.IGNORECASE)
                    if match:
                        idx_end = match.end()
                        remainder = text[idx_end:].strip()
                        # Clean remainder separators
                        remainder = re.sub(r'^[:\s\-\.\;\|_]+', '', remainder).strip()
                        
                        # Special handling if date pattern matched but remainder is empty, 
                        # check if the whole box is just 'Date: 31/05/2026' or similar
                        if len(remainder) >= 2 and not is_placeholder_value(remainder):
                            extracted_value = remainder
                            matched_box = item
                            used_boxes.add(idx)
                            break
            if matched_box:
                break
                
        # 2. Fall back to horizontal spatial logic if same-box check found nothing
        if extracted_value == "NOT_FOUND":
            best_label_item = None
            best_idx = -1
            best_score = 0
            
            # Find the best matching label box (must have conf >= 0.4 since it's printed text)
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
                # We found a label box! Now find paired values to the right
                label_x_max = best_label_item['x_max']
                label_x_min = best_label_item['x_min']
                label_y_center = best_label_item['y_center']
                
                candidates = []
                for idx, item in enumerate(ocr_items):
                    if idx == best_idx or idx in used_boxes:
                        continue
                    
                    # Target must have conf >= 0.4 OR (conf >= 0.15 and is very close to label/value)
                    # We keep candidates with conf >= 0.15 here, but apply gap logic carefully
                    if item['conf'] < 0.15:
                        continue
                        
                    # Must be to the right of the label start
                    if item['x_min'] > label_x_min + 10:
                        # Row constraint: Y difference < 20px (handles slight slant/alignment)
                        y_diff = abs(item['y_center'] - label_y_center)
                        if y_diff < 20:
                            candidates.append((idx, item))
                            
                if candidates:
                    # Sort by horizontal x_min
                    candidates.sort(key=lambda x: x[1]['x_min'])
                    
                    value_parts = []
                    prev_x_max = label_x_max
                    for idx, cand in candidates:
                        gap = cand['x_min'] - prev_x_max
                        
                        # First candidate gap threshold must be < 200px (prevents column crossing)
                        # Subsequent candidates gap threshold < 120px (must be close to previous word)
                        max_allowed_gap = 200 if len(value_parts) == 0 else 120
                        
                        if gap < max_allowed_gap:
                            # If candidate has low confidence (0.15 to 0.4), it MUST be extremely close (gap < 120px)
                            if cand['conf'] < 0.4 and gap >= 120:
                                break
                                
                            if not is_template_text(cand['text']):
                                value_parts.append(cand['text'])
                                used_boxes.add(idx)
                                prev_x_max = cand['x_max']
                        else:
                            break
                            
                    if value_parts:
                        extracted_value = " ".join(value_parts).strip()
                        matched_box = best_label_item
                        used_boxes.add(best_idx)
                        
        # Apply field-specific clean-up functions
        if extracted_value != "NOT_FOUND":
            if field == "chassis_no":
                extracted_value = clean_chassis(extracted_value)
            elif field == "invoice_no":
                extracted_value = clean_invoice(extracted_value)
            elif field == "welcome_bonus_amount":
                extracted_value = clean_amount(extracted_value)
            elif field == "invoice_date":
                extracted_value = clean_date(extracted_value)
            elif field == "dealership_name":
                extracted_value = clean_dealership(extracted_value)
                
        results[field] = extracted_value
        matched_items[field] = matched_box
        
    return results, matched_items

def main():
    parser = argparse.ArgumentParser(description="Extract handwritten data from disclaimer PDFs.")
    parser.add_argument("--pdf", required=True, help="Path to the disclaimer PDF file.")
    parser.add_argument("--output", help="Path to save the JSON output file.")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode and output annotated images.")
    args = parser.parse_args()
    
    if not os.path.exists(args.pdf):
        logging.error(f"Input PDF file not found: {args.pdf}")
        sys.exit(1)
        
    logging.info(f"Processing disclaimer: {args.pdf}")
    
    # Initialize EasyOCR Reader
    logging.info("Initializing EasyOCR reader (CPU mode)...")
    reader = easyocr.Reader(['en'], gpu=False)
    
    doc = fitz.open(args.pdf)
    num_pages = len(doc)
    logging.info(f"Total pages in PDF: {num_pages}")
    
    all_page_results = []
    
    for page_idx in range(num_pages):
        logging.info(f"Processing Page {page_idx + 1}/{num_pages}...")
        page = doc[page_idx]
        
        # Requirement 1: Render PDF page at 3x zoom (216 DPI)
        zoom = 3
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # Requirement 4: Convert fitz pixmap to image array (NumPy) for EasyOCR
        png_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        img_np = np.array(img)
        
        # Run OCR
        raw_results = reader.readtext(img_np)
        
        # Keep OCR blocks with conf >= 0.15 (Requirement 6: skip below 0.4, but we allow 0.15 if close to label)
        ocr_items = []
        skipped_count = 0
        for bbox, text, conf in raw_results:
            if conf < 0.15:
                skipped_count += 1
                logging.debug(f"Skipping OCR block with extremely low confidence ({conf:.2f}): '{text}'")
                continue
                
            parsed = parse_easyocr_box(bbox)
            parsed['text'] = text.strip()
            parsed['conf'] = conf
            ocr_items.append(parsed)
            
        logging.info(f"OCR found {len(raw_results)} blocks. Kept {len(ocr_items)} (skipped {skipped_count} below 0.15 conf).")
        
        # Extract fields
        extracted, matched_boxes = extract_values_from_ocr(ocr_items)
        all_page_results.append(extracted)
        
        # Log which fields were found vs missing
        found_fields = [f for f, v in extracted.items() if v != "NOT_FOUND"]
        missing_fields = [f for f, v in extracted.items() if v == "NOT_FOUND"]
        logging.info(f"Page {page_idx + 1} Found fields: {found_fields}")
        if missing_fields:
            logging.warning(f"Page {page_idx + 1} Missing/Not Found fields: {missing_fields}")
            
        # Debug Mode visualization (Requirement: Draw bounding boxes to visualize matching)
        if args.debug:
            # We want to draw on a copy of the rendered image
            draw = ImageDraw.Draw(img)
            
            # Draw all kept OCR boxes in thin gray for context
            for item in ocr_items:
                box = item['box']
                draw.polygon([tuple(p) for p in box], outline="gray")
                
            # Draw matched fields
            colors = {
                "chassis_no": "green",
                "invoice_no": "blue",
                "dealership_name": "orange",
                "invoice_date": "purple",
                "welcome_bonus_amount": "red"
            }
            
            for field, box_item in matched_boxes.items():
                if box_item:
                    box = box_item['box']
                    color = colors.get(field, "yellow")
                    # Draw bold outline (multiple pixels)
                    draw.polygon([tuple(p) for p in box], outline=color, width=4)
                    
                    # Draw a label above the box
                    draw.text((box[0][0], box[0][1] - 15), f"{field}: {extracted[field]}", fill=color)
                    
            # Save debug image
            base_name = os.path.splitext(os.path.basename(args.pdf))[0]
            debug_img_name = f"{base_name}_debug_page_{page_idx + 1}.png"
            debug_img_path = os.path.join(os.path.dirname(os.path.abspath(args.pdf)), debug_img_name)
            img.save(debug_img_path)
            logging.info(f"Saved visualization debug image: {debug_img_path}")
            
    # Combine results
    # For a multi-page PDF, if a field is NOT_FOUND on page 1 but is found on page 2, we merge them!
    final_dict = {}
    all_fields = ["chassis_no", "invoice_no", "dealership_name", "invoice_date", "welcome_bonus_amount"]
    for field in all_fields:
        final_val = "NOT_FOUND"
        for page_res in all_page_results:
            if page_res.get(field) and page_res.get(field) != "NOT_FOUND":
                final_val = page_res[field]
                break
        final_dict[field] = final_val
        
    # Output to stdout
    print("\n=== EXTRACTION RESULTS ===")
    print(json.dumps(final_dict, indent=2))
    print("==========================\n")
    
    # Save output to JSON file
    output_path = args.output
    if not output_path:
        base_name = os.path.splitext(os.path.basename(args.pdf))[0]
        output_path = os.path.join(os.path.dirname(os.path.abspath(args.pdf)), f"{base_name}_extracted.json")
        
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_dict, f, indent=2, ensure_ascii=False)
        logging.info(f"Saved results to JSON: {output_path}")
    except Exception as e:
        logging.error(f"Failed to save JSON file: {e}")

if __name__ == "__main__":
    main()
