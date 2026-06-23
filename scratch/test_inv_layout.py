import cv2
import fitz
import easyocr
import numpy as np
import os
import sys
import re

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def find_text_regions(results, target_queries):
    found_regions = []
    # results format: [([[x0,y0], [x1,y1], [x2,y2], [x3,y3]], text, confidence), ...]
    for box, text, conf in results:
        text_clean = text.lower().strip()
        for query in target_queries:
            if query in text_clean:
                # Get bounding box
                xs = [pt[0] for pt in box]
                ys = [pt[1] for pt in box]
                xmin, xmax = int(min(xs)), int(max(xs))
                ymin, ymax = int(min(ys)), int(max(ys))
                found_regions.append({
                    "query": query,
                    "text": text,
                    "box": (xmin, ymin, xmax, ymax),
                    "conf": conf
                })
    return found_regions

pdf_path = "documents/G NIVETHA/INV-1781414252482.pdf"
doc = fitz.open(pdf_path)
page = doc.load_page(0)
pix = page.get_pixmap(dpi=150) # Use 150 DPI for layout analysis
img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)

# Run EasyOCR with word details
reader = easyocr.Reader(['en'], gpu=False)
results = reader.readtext(img, paragraph=False)

print("\n--- Found Target Text Anchors ---")
targets = ["customer name", "dealer name", "signature", "seal", "stamp", "anantcars"]
found = find_text_regions(results, targets)
for f in found:
    print(f"Match for '{f['query']}': '{f['text']}' at box {f['box']}")

# Now let's check for blue pixels around specific regions
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
lower_blue = np.array([90, 80, 80])
upper_blue = np.array([130, 255, 255])
mask = cv2.inRange(hsv, lower_blue, upper_blue)

h, w, _ = img.shape
print(f"\nImage size: width={w}, height={h}")
total_blue = np.sum(mask > 0)
print(f"Total blue pixels in whole image (with 90,80,80 threshold): {total_blue}")

# Let's inspect regions around "Customer Signature" or "Dealer Name" / "anantcars"
# Typically stamps/signatures are below or near these labels.
# Let's search a window below/around them (e.g. within 200 pixels vertically/horizontally)
for f in found:
    box = f["box"]
    # We want to crop a search window around the box
    # For "customer signature", signature is usually above or below it. Let's expand search window.
    # Let's expand window by 100 pixels in all directions, and 200 pixels below.
    win_ymin = max(0, box[1] - 100)
    win_ymax = min(h, box[3] + 200)
    win_xmin = max(0, box[0] - 150)
    win_xmax = min(w, box[2] + 150)
    
    region_mask = mask[win_ymin:win_ymax, win_xmin:win_xmax]
    region_blue_pixels = np.sum(region_mask > 0)
    print(f"Blue pixels in region around '{f['text']}' (win: y:[{win_ymin},{win_ymax}], x:[{win_xmin},{win_xmax}]): {region_blue_pixels}")
    
    # Save the region crop to debug
    if region_blue_pixels > 100:
        crop_img = img[win_ymin:win_ymax, win_xmin:win_xmax]
        crop_path = f"scratch/region_{f['query']}.png"
        cv2.imwrite(crop_path, crop_img)
        print(f"  Saved region crop to {crop_path}")
