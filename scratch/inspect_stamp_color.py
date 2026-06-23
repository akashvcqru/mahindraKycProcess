import cv2
import numpy as np
import fitz

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\ABILASHGOWDA A\DISC -1781516436736.pdf"
doc = fitz.open(pdf_path)
page = doc.load_page(0)
pix = page.get_pixmap(dpi=300)
img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
h, w, _ = img.shape

bottom_y = int(0.6 * h)
bottom_crop = img[bottom_y:h, 0:w]
hsv = cv2.cvtColor(bottom_crop, cv2.COLOR_BGR2HSV)

# Define color ranges to check:
# Blue/Purple
lower_blue = np.array([90, 50, 50])
upper_blue = np.array([130, 255, 255])
mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
blue_pixels = np.sum(mask_blue > 0)

# Red/Pink
lower_red1 = np.array([0, 50, 50])
upper_red1 = np.array([10, 255, 255])
lower_red2 = np.array([170, 50, 50])
upper_red2 = np.array([180, 255, 255])
mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
mask_red = mask_red1 | mask_red2
red_pixels = np.sum(mask_red > 0)

# Green
lower_green = np.array([35, 50, 50])
upper_green = np.array([85, 255, 255])
mask_green = cv2.inRange(hsv, lower_green, upper_green)
green_pixels = np.sum(mask_green > 0)

# Black/Dark gray (Value < 100)
lower_black = np.array([0, 0, 0])
upper_black = np.array([180, 255, 100])
mask_black = cv2.inRange(hsv, lower_black, upper_black)
black_pixels = np.sum(mask_black > 0)

print(f"Bottom crop dimensions: {w}x{h - bottom_y}")
print(f"Blue/Purple pixels: {blue_pixels}")
print(f"Red/Pink pixels: {red_pixels}")
print(f"Green pixels: {green_pixels}")
print(f"Black/Dark pixels: {black_pixels}")
