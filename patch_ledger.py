import re

with open('automate_login.py', 'r', encoding='utf-8') as f:
    full_text = f.read()

# 1. Update OpenAI retry logic to include exponential backoff
openai_retry_target = r'''        except Exception as e:
            if retry_attempt == max_retries - 1:
                logging.error\(
                    f"OpenAI Vision API extraction failed after \{max_retries\} attempts for \{os\.path\.basename\(pdf_path\)\}: \{e\}"
                \)
                return None
            else:
                logging.warning\(
                    f"Attempt \{retry_attempt \+ 1\} failed for \{os\.path\.basename\(pdf_path\)\}: \{e\}\. Retrying\.\.\."
                \)
                import time

                time\.sleep\(1\)  # Brief delay before retry'''

openai_retry_replacement = r'''        except Exception as e:
            if retry_attempt == max_retries - 1:
                logging.error(
                    f"OpenAI Vision API extraction failed after {max_retries} attempts for {os.path.basename(pdf_path)}: {e}"
                )
                return None
            else:
                logging.warning(
                    f"Attempt {retry_attempt + 1} failed for {os.path.basename(pdf_path)}: {e}. Retrying..."
                )
                import time
                # Exponential backoff for 429 Too Many Requests
                if "429" in str(e) or "Too Many Requests" in str(e):
                    backoff_time = 5 * (2 ** retry_attempt) # 5s, 10s
                    logging.warning(f"Rate limit hit. Waiting {backoff_time}s before retry...")
                    time.sleep(backoff_time)
                else:
                    time.sleep(2)  # Brief delay before retry'''

full_text = re.sub(openai_retry_target, openai_retry_replacement, full_text, count=1)

# Do the same for Portal Validation OpenAI retry... wait, Portal Validation doesn't have a retry loop!
# It just does `response.raise_for_status()`. I'll leave it for now to focus on Ledger.

# 2. Add Ledger visual extraction helper function
ledger_helper = r'''def extract_ledger_visual(file_path, extracted_name):
    """
    Fallback visual extractor for Ledgers when OpenAI fails.
    Uses EasyOCR to find the bounding box of the extracted customer name and crops it.
    """
    import fitz
    import numpy as np
    from PIL import Image
    import io
    import base64
    from rapidfuzz import fuzz

    visual_extractions = {}
    if not extracted_name or extracted_name == "NOT_FOUND":
        return visual_extractions

    try:
        reader = get_ocr_reader()
        doc = fitz.open(file_path)
        
        # Only process first page for ledger name usually
        page = doc[0]
        zoom = 3
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        img_np = np.array(img)

        raw_results = reader.readtext(img_np)
        
        best_score = 0
        best_box = None
        
        target_name_clean = "".join([c for c in extracted_name.lower() if c.isalnum() or c.isspace()])

        for bbox, text, conf in raw_results:
            if conf < 0.1:
                continue
            
            text_clean = "".join([c for c in text.lower() if c.isalnum() or c.isspace()])
            score = fuzz.partial_ratio(target_name_clean, text_clean)
            
            if score > best_score:
                best_score = score
                best_box = bbox

        if best_box and best_score > 70:
            x_coords = [p[0] for p in best_box]
            y_coords = [p[1] for p in best_box]
            x1 = max(0, min(x_coords) - 15)
            y1 = max(0, min(y_coords) - 15)
            x2 = min(img_np.shape[1], max(x_coords) + 15)
            y2 = min(img_np.shape[0], max(y_coords) + 15)
            
            cropped = img.crop((x1, y1, x2, y2))
            buf = io.BytesIO()
            cropped.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            
            visual_extractions["customer_signature"] = {
                'value': extracted_name,
                'confidence': conf * 100 if conf else 80,
                'bbox': [x1, y1, x2, y2],
                'image_base64': b64
            }
    except Exception as e:
        import logging
        logging.error(f"Failed to extract ledger visual crop: {e}")
        
    return visual_extractions
'''

# 3. Patch `elif is_ledger:`
ledger_target = r'''    elif is_ledger:
        result\["file_type"\] = "LEDGER"
        extracted_name, name_score = extract_best_name\(text, claim_customer_name\)
        result\["extracted_data"\] = \{"Customer Name": extracted_name\}
        result\["validations"\] = \{
            "Name Match Score": name_score,
            "Name Match Status": "MATCH" if name_score >= 80 else "MISMATCH",
        \}'''

ledger_replacement = r'''    elif is_ledger:
        result["file_type"] = "LEDGER"
        extracted_name, name_score = extract_best_name(text, claim_customer_name)
        result["extracted_data"] = {"Customer Name": extracted_name}
        
        # Add visual extraction fallback for Ledger
        try:
            ledger_visuals = extract_ledger_visual(file_path, extracted_name)
            if ledger_visuals:
                result["extracted_data"]["visual_extractions"] = ledger_visuals
        except Exception as e:
            logging.error(f"Error in ledger visual extraction fallback: {e}")
            
        result["validations"] = {
            "Name Match Score": name_score,
            "Name Match Status": "MATCH" if name_score >= 80 else "MISMATCH",
        }'''

# Insert helper function right before `def classify_and_extract`
classify_target = r'(def classify_and_extract\()'
full_text = re.sub(classify_target, ledger_helper + '\n\\1', full_text, count=1)

# Patch the logic
full_text = re.sub(ledger_target, ledger_replacement, full_text, count=1)

with open('automate_login.py', 'w', encoding='utf-8') as f:
    f.write(full_text)

print("Successfully patched automate_login.py for ledger visuals and backoff")
