"""
preprocessing/deskew.py
========================
Detects and corrects page rotation/skew using OpenCV.
Supports up to ±45 degrees of rotation correction.
"""
import logging
import numpy as np

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    logging.warning("[deskew] opencv-python not installed. Deskew will be skipped.")


def deskew_image(pil_image):
    """
    Detect and correct skew/rotation in a scanned page image.
    
    Args:
        pil_image: PIL.Image object (RGB or grayscale)
    
    Returns:
        PIL.Image: Deskewed image (same mode as input). Returns original if
                   opencv is unavailable or correction is < 0.3 degrees.
    """
    if not _CV2_AVAILABLE:
        return pil_image

    try:
        from PIL import Image
        import cv2

        # Convert PIL to numpy array for OpenCV
        img_array = np.array(pil_image.convert("L"))  # grayscale

        # Threshold to binary
        _, thresh = cv2.threshold(img_array, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Find all non-zero (text) pixel coordinates
        coords = np.column_stack(np.where(thresh > 0))
        if coords.size == 0:
            return pil_image

        # Compute minimum area rectangle enclosing the text pixels
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]

        # Normalize angle to [-45, 45] range
        if angle < -45:
            angle = angle + 90
        elif angle > 45:
            angle = angle - 90

        # Skip tiny corrections to avoid artifacts on clean scans
        if abs(angle) < 0.3:
            return pil_image

        logging.info(f"[deskew] Correcting page skew by {angle:.2f} degrees")

        # Rotate around center
        h, w = img_array.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Apply rotation to the original color image
        orig_array = np.array(pil_image)
        rotated = cv2.warpAffine(
            orig_array, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )

        return Image.fromarray(rotated)

    except Exception as e:
        logging.warning(f"[deskew] Error during deskew: {e}. Returning original.")
        return pil_image
