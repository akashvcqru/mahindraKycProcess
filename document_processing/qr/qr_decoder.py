"""
qr/qr_decoder.py
=================
Decodes QR codes and barcodes from a PIL Image using OpenCV.
The tax invoice has 2 QR codes:
  - Top-right: Electronic Reference Number (e-invoice URL or IRN)
  - Bottom-left: Mahindra service feedback QR

Falls back gracefully if opencv-python is not installed.
"""
import logging
import numpy as np

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    logging.warning("[qr_decoder] opencv-python not installed. QR decoding unavailable.")


def decode_qr(pil_image) -> list:
    """
    Detect and decode all QR codes / barcodes in a PIL Image.

    Args:
        pil_image: PIL.Image (RGB)

    Returns:
        list[str]: Decoded QR content strings (one per QR found).
                   Empty list if none found or opencv unavailable.
    """
    if not _CV2_AVAILABLE:
        return []

    try:
        img_array = np.array(pil_image.convert("RGB"))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        detector = cv2.QRCodeDetector()
        # detectAndDecodeMulti returns (retval, decoded_list, points, straight_qrcode)
        retval, decoded_list, points, _ = detector.detectAndDecodeMulti(gray)

        results = []
        if retval and decoded_list:
            for text in decoded_list:
                if text and text.strip():
                    results.append(text.strip())
                    logging.info(f"[qr_decoder] QR decoded: {text[:80]}...")

        if not results:
            logging.debug("[qr_decoder] No QR codes detected in image")

        return results

    except Exception as e:
        logging.warning(f"[qr_decoder] QR decode error: {e}")
        return []


def decode_qr_from_region(pil_image, top: float, left: float,
                           bottom: float, right: float) -> list:
    """
    Crop a region (fractions of image size) and decode QR codes within it.
    Useful for targeting specific areas (e.g. top-right corner of invoice).

    Args:
        pil_image:         PIL.Image (RGB)
        top, left, bottom, right: Fractions (0.0-1.0) of image dimensions

    Returns:
        list[str]: Decoded QR content strings
    """
    w, h = pil_image.size
    box = (
        int(left * w),
        int(top * h),
        int(right * w),
        int(bottom * h),
    )
    cropped = pil_image.crop(box)
    return decode_qr(cropped)
