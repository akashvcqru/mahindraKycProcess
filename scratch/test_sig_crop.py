import cv2
import fitz
import numpy as np
import os
import sys

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

pdf_path = "documents/G NIVETHA/INV-1781414252482.pdf"
doc = fitz.open(pdf_path)
page = doc.load_page(0)
pix = page.get_pixmap(dpi=300) # 300 DPI
img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)

h, w, _ = img.shape
print(f"Image shape: {img.shape}")

# Let's locate the word 'Signature' in the high-res image
# At 150 DPI it was at box (151, 1371, 261, 1387)
# At 300 DPI, we expect it to be around double that: x: [302, 522], y: [2742, 2774]
# Let's crop a window around this area: y from 2500 to 3200, x from 0 to 800
crop_ymin = 2500
crop_ymax = 3200
crop_xmin = 0
crop_xmax = 900

crop = img[crop_ymin:crop_ymax, crop_xmin:crop_xmax]
cv2.imwrite("scratch/inv_sig_area_300.png", crop)
print("Saved high-res signature area to scratch/inv_sig_area_300.png")

# Now let's run blue ink detection on this crop
hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
lower_blue = np.array([90, 50, 50]) # Wider range
upper_blue = np.array([130, 255, 255])
mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
blue_pixels = np.sum(mask_blue > 0)
print(f"Blue/purple pixels count in crop: {blue_pixels}")

# Let's also run dark/black ink detection (signatures can be in black/blue pen)
# For dark/black ink, we check for pixels with low value (brightness) and low saturation
# E.g. Value < 80, Saturation < 50
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
# Let's exclude printed text by only looking at regions that are not part of printed labels if possible,
# or simply counting dark pixels that aren't the printed words.
# Actually, let's see if we can find blue/purple ink first since that's standard for stamps/signatures.
# We'll also test lower saturation for faint blue/purple:
lower_blue_faint = np.array([90, 30, 30])
upper_blue_faint = np.array([130, 255, 255])
mask_blue_faint = cv2.inRange(hsv, lower_blue_faint, upper_blue_faint)
blue_pixels_faint = np.sum(mask_blue_faint > 0)
print(f"Faint blue/purple pixels count in crop: {blue_pixels_faint}")
