import cv2
import fitz
import easyocr
import numpy as np
import os
import sys
import re
from rapidfuzz import fuzz

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def find_blue_ink_clusters(img_path):
    print(f"Finding blue clusters in {img_path}...")
    img = cv2.imread(img_path)
    if img is None:
        print("Error: image not found")
        return []
        
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # We use a threshold for blue ink
    lower_blue = np.array([90, 80, 80])
    upper_blue = np.array([130, 255, 255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    
    # Let's run connected components on the mask to find clusters
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
    
    clusters = []
    # stats format: [x, y, w, h, area]
    for i in range(1, num_labels): # 0 is background
        area = stats[i, cv2.CC_STAT_AREA]
        # Ignore tiny noise or huge blocks (like table borders if any are blue)
        if 50 < area < 20000:
            x = stats[i, cv2.CC_STAT_LEFT]
            y = stats[i, cv2.CC_STAT_TOP]
            w = stats[i, cv2.CC_STAT_WIDTH]
            h = stats[i, cv2.CC_STAT_HEIGHT]
            clusters.append((x, y, w, h, area))
            
    print(f"Found {len(clusters)} raw blue clusters.")
    # Merge overlapping/nearby clusters
    merged = []
    for c in sorted(clusters, key=lambda item: item[4], reverse=True): # sort by area descending
        # check if it overlaps with an existing merged cluster or is very close (within 100 pixels)
        x1, y1, w1, h1, a1 = c
        inserted = False
        for idx, (mx, my, mw, mh, ma) in enumerate(merged):
            # check distance
            if not (x1 + w1 + 100 < mx or mx + mw + 100 < x1 or y1 + h1 + 100 < my or my + mh + 100 < y1):
                # merge
                nx = min(x1, mx)
                ny = min(y1, my)
                nw = max(x1+w1, mx+mw) - nx
                nh = max(y1+h1, my+mh) - ny
                merged[idx] = (nx, ny, nw, nh, ma + a1)
                inserted = True
                break
        if not inserted:
            merged.append((x1, y1, w1, h1, a1))
            
    print(f"After merging nearby clusters, found {len(merged)} clusters:")
    for idx, m in enumerate(merged):
        print(f" Cluster {idx}: x={m[0]}, y={m[1]}, w={m[2]}, h={m[3]}, total_area={m[4]}")
    return merged

def test_ocr_on_clusters():
    bottom_crop_path = "scratch/inv_bottom_crop.png"
    if not os.path.exists(bottom_crop_path):
        print("Bottom crop does not exist. Please run test_inv_ocr_regions.py first.")
        return
        
    img = cv2.imread(bottom_crop_path)
    h, w, _ = img.shape
    
    clusters = find_blue_ink_clusters(bottom_crop_path)
    reader = easyocr.Reader(['en'], gpu=False)
    
    for idx, (cx, cy, cw, ch, area) in enumerate(clusters):
        if area < 200:
            # Skip very small noise
            continue
            
        print(f"\n==========================================")
        print(f"OCR ON CLUSTER {idx}: x={cx}, y={cy}, w={cw}, h={ch}, area={area}")
        print(f"==========================================")
        
        # Expand slightly
        ymin = max(0, cy - 20)
        ymax = min(h, cy + ch + 20)
        xmin = max(0, cx - 20)
        xmax = min(w, cx + cw + 20)
        
        crop = img[ymin:ymax, xmin:xmax]
        crop_name = f"scratch/inv_cluster_{idx}.png"
        cv2.imwrite(crop_name, crop)
        print(f"Saved cluster crop to {crop_name}")
        
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
            print(f"  Angle {angle}: {results}")
            for text_line in results:
                words = [wd.upper() for wd in re.sub(r'[^A-Za-z]', ' ', text_line).split() if len(wd) >= 3]
                stamp_words.extend(words)
        print(f"  All extracted words for Cluster {idx}: {set(stamp_words)}")

test_ocr_on_clusters()
