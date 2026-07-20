"""
signature/detector.py
======================
Detects the presence of handwritten signatures and circular stamps
in a document image using OpenCV contour and blob analysis.

This is PRESENCE-ONLY detection (yes/no).
It does NOT transcribe the signature text (that would need TrOCR).

Strategy:
  - Stamps:     Detect large circular/oval contours with high aspect ratio
                in the stamp region (typically bottom-left or bottom-right)
  - Signatures: Detect irregular ink blobs with low rectangularity score
                (handwriting has jagged, non-rectangular contours vs printed text)
"""
import logging
import numpy as np

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    logging.warning("[signature.detector] opencv-python not installed. Detection unavailable.")


def detect_signature_and_stamp(pil_image,
                                stamp_region: tuple = None,
                                sig_region: tuple = None) -> dict:
    """
    Detect presence of stamp and handwritten signature in a PIL Image.

    Args:
        pil_image:    PIL.Image (RGB) — full page or pre-cropped region
        stamp_region: (top, left, bottom, right) as fractions 0.0-1.0
                      If None, scans full image for stamp
        sig_region:   (top, left, bottom, right) as fractions 0.0-1.0
                      If None, scans full image for signature

    Returns:
        dict: {
            "stamp_present":     bool,
            "stamp_confidence":  float,   # 0.0-1.0
            "sig_present":       bool,
            "sig_confidence":    float,   # 0.0-1.0
        }
    """
    if not _CV2_AVAILABLE:
        return {
            "stamp_present": False, "stamp_confidence": 0.0,
            "sig_present": False,   "sig_confidence": 0.0,
        }

    try:
        stamp_result = _detect_stamp(pil_image, stamp_region)
        sig_result   = _detect_signature(pil_image, sig_region)
        return {**stamp_result, **sig_result}
    except Exception as e:
        logging.error(f"[signature.detector] Detection error: {e}")
        return {
            "stamp_present": False, "stamp_confidence": 0.0,
            "sig_present": False,   "sig_confidence": 0.0,
        }


def _crop_region(pil_image, region):
    """Crop PIL image to a fractional region (top, left, bottom, right)."""
    if region is None:
        return pil_image
    w, h = pil_image.size
    top, left, bottom, right = region
    box = (int(left * w), int(top * h), int(right * w), int(bottom * h))
    return pil_image.crop(box)


def _detect_stamp(pil_image, region) -> dict:
    """
    Detect a circular/oval rubber stamp using a 3-factor approach:
    1. HSV Color Mask  — detect blue/purple ink regions (dealer stamps use colored ink)
    2. Contour Shape   — circularity check with relaxed threshold (handles smudged/ovals)
    3. Text Density    — confirm ink text exists inside the detected region

    Combining all 3 dramatically reduces false positives on watermarks/logos.

    Returns dict with stamp_present (bool) and stamp_confidence (float 0.0-1.0).
    """
    img = _crop_region(pil_image, region)
    img_array = np.array(img.convert("RGB"))
    gray = np.array(img.convert("L"))

    # ── Factor 1: HSV Color Mask (blue/purple ink) ────────────────────────────
    img_hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
    # Blue range: H=100-130, Purple range: H=130-160, S>40, V>40
    blue_mask   = cv2.inRange(img_hsv, np.array([100, 40, 40]), np.array([130, 255, 255]))
    purple_mask = cv2.inRange(img_hsv, np.array([130, 30, 40]), np.array([165, 255, 255]))
    # Also detect dark blue (near-black blue stamps)
    dark_blue_mask = cv2.inRange(img_hsv, np.array([100, 30, 20]), np.array([130, 180, 120]))
    color_mask = cv2.bitwise_or(blue_mask, cv2.bitwise_or(purple_mask, dark_blue_mask))

    # Dilate color mask to connect nearby colored pixels
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    color_mask_dilated = cv2.dilate(color_mask, kernel, iterations=3)

    color_pixel_ratio = float(np.sum(color_mask > 0)) / max(gray.size, 1)
    color_score = min(1.0, color_pixel_ratio * 100)   # Normalize to 0-1

    # ── Factor 2: Contour Circularity (relaxed threshold for ovals/smudged) ───
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 120)   # Lower thresholds for smudged edges

    # Also run Canny on the color mask to catch colored stamp outlines
    color_edges = cv2.Canny(color_mask_dilated, 40, 120)
    combined_edges = cv2.bitwise_or(edges, color_edges)

    contours, _ = cv2.findContours(combined_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_shape_score = 0.0
    stamp_bbox = None
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 800:   # Too small
            continue
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue

        # Circularity: 4π·Area / Perimeter² (1.0 = perfect circle)
        circularity = (4 * np.pi * area) / (perimeter ** 2)

        # Relaxed threshold: 0.40 handles ovals, partial, and smudged stamps
        if circularity > 0.40:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect = min(w, h) / max(w, h) if max(w, h) > 0 else 0
            if aspect > 0.35 and min(w, h) > 30:
                shape_score = min(1.0, circularity * aspect * 1.2)
                if shape_score > best_shape_score:
                    best_shape_score = shape_score
                    stamp_bbox = (x, y, w, h)

    # ── Factor 3: Text Density inside detected stamp region ──────────────────
    text_density_score = 0.0
    if stamp_bbox is not None:
        x, y, w, h = stamp_bbox
        # Add generous padding around the contour bbox
        pad = 20
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(gray.shape[1], x + w + pad), min(gray.shape[0], y + h + pad)
        roi = gray[y1:y2, x1:x2]
        if roi.size > 0:
            # Threshold to binary: dark pixels = ink
            _, binary = cv2.threshold(roi, 180, 255, cv2.THRESH_BINARY_INV)
            dark_ratio = float(np.sum(binary > 0)) / binary.size
            # Dark pixel ratio 2-25% = typical stamp (sparse text, not solid fill)
            if 0.02 <= dark_ratio <= 0.35:
                text_density_score = min(1.0, dark_ratio * 8)
            elif dark_ratio > 0.35:
                text_density_score = 0.3   # Probably a solid watermark, not stamp

    # ── Combine factors into weighted confidence ──────────────────────────────
    # Shape is required; color and text density boost confidence
    if best_shape_score > 0:
        # Weighted: shape(50%) + color(30%) + text_density(20%)
        combined = (best_shape_score * 0.50 +
                    color_score      * 0.30 +
                    text_density_score * 0.20)
    elif color_score > 0.15:
        # Color-only fallback: if we see colored ink but no clear circle shape,
        # report low confidence (UNKNOWN territory)
        combined = color_score * 0.35
    else:
        combined = 0.0

    combined = min(1.0, combined)
    present = combined >= 0.35   # Hard threshold for PASS

    logging.debug(
        f"[signature.detector] Stamp: present={present}, confidence={combined:.3f} "
        f"(shape={best_shape_score:.2f}, color={color_score:.2f}, density={text_density_score:.2f})"
    )
    return {"stamp_present": present, "stamp_confidence": round(combined, 3)}


def _detect_signature(pil_image, region) -> dict:
    """
    Detect handwritten signature by finding irregular ink blobs
    with low rectangularity (handwriting is not box-shaped).
    """
    img = _crop_region(pil_image, region)
    img_array = np.array(img.convert("L"))

    # Invert and threshold: dark ink on white background
    _, binary = cv2.threshold(img_array, 180, 255, cv2.THRESH_BINARY_INV)

    # Dilate to connect signature strokes
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    dilated = cv2.dilate(binary, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Score: look for medium-large irregular blobs (not rectangular = not printed text)
    signature_score = 0.0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 300 or area > 50000:
            continue  # Too small (noise) or too large (border)

        x, y, w, h = cv2.boundingRect(cnt)
        if w < 20 or h < 8:
            continue

        # Rectangularity: how much of the bounding box is filled
        rect_area = w * h
        rectangularity = area / rect_area if rect_area > 0 else 1.0

        # Handwriting: medium fill, wider than tall
        if 0.1 < rectangularity < 0.65 and w > h:
            score = (1 - rectangularity) * min(area / 5000, 1.0)
            signature_score = max(signature_score, score)

    present = signature_score >= 0.25
    logging.debug(f"[signature.detector] Signature: present={present}, score={signature_score:.2f}")
    return {"sig_present": present, "sig_confidence": round(signature_score, 3)}
