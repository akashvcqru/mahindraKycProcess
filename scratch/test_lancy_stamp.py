import cv2
import fitz
import numpy as np

def check_blue_pixels(pdf_path, lower_sat, lower_val):
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=300)
    
    img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Try different thresholds
    lower_blue = np.array([90, lower_sat, lower_val])
    upper_blue = np.array([130, 255, 255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    
    blue_pixels = np.sum(mask > 0)
    print(f"Threshold Sat>={lower_sat}, Val>={lower_val} -> Blue pixels: {blue_pixels}")
    
    if blue_pixels > 0:
        pts = np.argwhere(mask > 0)
        ymin, xmin = pts.min(axis=0)
        ymax, xmax = pts.max(axis=0)
        print(f"Bounding box: ymin={ymin}, xmin={xmin}, ymax={ymax}, xmax={xmax}")

pdf_path = "documents/LANCY BABU P/LANCY LEDGER-1781348080305.pdf"
print("Checking pixels for Lancy Ledger...")
for sat in [80, 50, 30, 10]:
    for val in [80, 50, 30, 10]:
        check_blue_pixels(pdf_path, sat, val)
