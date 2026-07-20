"""
preprocessing/image_quality.py
================================
Pre-OCR image quality assessment.
Calculates a 0-100 quality score from blur, brightness, contrast, and noise.

If quality_score < 40, the image is too degraded for reliable OCR and
the validation result should be UNKNOWN (not FAIL) pending manual review.

Usage:
    from document_processing.preprocessing.image_quality import score_image_quality
    result = score_image_quality(pil_image)
    # result = {
    #   "score": 72,          # overall 0-100
    #   "blur_score": 0.85,   # 0.0 (very blurry) to 1.0 (sharp)
    #   "brightness_score": 0.70,  # 0.0 (dark/washed) to 1.0 (optimal)
    #   "contrast_score": 0.60,    # 0.0 (flat) to 1.0 (rich contrast)
    #   "noise_score": 0.75,       # 0.0 (very noisy) to 1.0 (clean)
    #   "low_quality": False,      # True if score < QUALITY_HOLD_THRESHOLD
    #   "reason": ""              # human-readable reason if low_quality
    # }
"""

import logging
import numpy as np

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    logging.warning("[image_quality] opencv-python not installed. Quality scoring unavailable.")

# Threshold below which the scan is considered too degraded for reliable OCR
QUALITY_HOLD_THRESHOLD = 40

# Weights for the overall score (must sum to 1.0)
_WEIGHTS = {
    "blur":       0.40,   # Most important — blurry text is unreadable
    "brightness": 0.20,   # Very dark or washed-out kills OCR
    "contrast":   0.25,   # Low contrast text blends into background
    "noise":      0.15,   # Heavy grain confuses OCR
}

# Optimal brightness range (0-255 grayscale mean)
_BRIGHTNESS_LOW  = 60    # Below this = too dark
_BRIGHTNESS_HIGH = 230   # Above this = too washed out / overexposed
_BRIGHTNESS_OPT_LOW  = 130  # Optimal range start
_BRIGHTNESS_OPT_HIGH = 210  # Optimal range end

# Blur: Laplacian variance threshold
_BLUR_SHARP_THRESHOLD = 300   # Variance above this = sharp
_BLUR_ACCEPT_THRESHOLD = 50   # Variance below this = very blurry

# Contrast: std deviation threshold
_CONTRAST_RICH_THRESHOLD = 70   # Std dev above this = rich contrast
_CONTRAST_FLAT_THRESHOLD = 20   # Std dev below this = flat/grey


def score_image_quality(pil_image) -> dict:
    """
    Calculate a composite image quality score for a scanned document page.

    Args:
        pil_image: PIL.Image (any mode — will be converted to grayscale internally)

    Returns:
        dict: Quality metrics and overall score (0-100)
    """
    if not _CV2_AVAILABLE:
        # Return a neutral score if OpenCV is not available
        return {
            "score": 70,
            "blur_score": 0.7,
            "brightness_score": 0.7,
            "contrast_score": 0.7,
            "noise_score": 0.7,
            "low_quality": False,
            "reason": "OpenCV not available — quality check skipped",
        }

    try:
        from PIL import Image

        # Convert to grayscale numpy array for all calculations
        gray = np.array(pil_image.convert("L"), dtype=np.float32)

        blur_s   = _score_blur(gray)
        bright_s = _score_brightness(gray)
        cont_s   = _score_contrast(gray)
        noise_s  = _score_noise(gray)

        overall = (
            blur_s   * _WEIGHTS["blur"]       +
            bright_s * _WEIGHTS["brightness"] +
            cont_s   * _WEIGHTS["contrast"]   +
            noise_s  * _WEIGHTS["noise"]
        ) * 100.0
        overall = max(0.0, min(100.0, overall))

        low_quality = overall < QUALITY_HOLD_THRESHOLD
        reason = ""
        if low_quality:
            parts = []
            if blur_s < 0.35:
                parts.append(f"image is blurry (blur={blur_s:.2f})")
            if bright_s < 0.35:
                parts.append(f"poor brightness (brightness={bright_s:.2f})")
            if cont_s < 0.35:
                parts.append(f"low contrast (contrast={cont_s:.2f})")
            if noise_s < 0.35:
                parts.append(f"high noise (noise={noise_s:.2f})")
            reason = "Low quality: " + "; ".join(parts) if parts else "Score below threshold"

        result = {
            "score":            round(overall, 1),
            "blur_score":       round(blur_s, 3),
            "brightness_score": round(bright_s, 3),
            "contrast_score":   round(cont_s, 3),
            "noise_score":      round(noise_s, 3),
            "low_quality":      low_quality,
            "reason":           reason,
        }

        level = "LOW" if low_quality else "OK"
        logging.info(
            f"[image_quality] Score={overall:.1f}/100 [{level}] "
            f"blur={blur_s:.2f} bright={bright_s:.2f} contrast={cont_s:.2f} noise={noise_s:.2f}"
        )
        return result

    except Exception as e:
        logging.warning(f"[image_quality] Quality scoring failed: {e}. Returning neutral.")
        return {
            "score": 70,
            "blur_score": 0.7,
            "brightness_score": 0.7,
            "contrast_score": 0.7,
            "noise_score": 0.7,
            "low_quality": False,
            "reason": f"Quality scoring error: {e}",
        }


def _score_blur(gray: np.ndarray) -> float:
    """
    Measure sharpness using Laplacian variance.
    Higher variance = sharper edges = better.
    Returns 0.0 (blurry) to 1.0 (sharp).
    """
    try:
        laplacian_var = float(cv2.Laplacian(gray.astype(np.uint8), cv2.CV_64F).var())
        if laplacian_var >= _BLUR_SHARP_THRESHOLD:
            return 1.0
        elif laplacian_var <= _BLUR_ACCEPT_THRESHOLD:
            return 0.0
        else:
            return (laplacian_var - _BLUR_ACCEPT_THRESHOLD) / (_BLUR_SHARP_THRESHOLD - _BLUR_ACCEPT_THRESHOLD)
    except Exception:
        return 0.7


def _score_brightness(gray: np.ndarray) -> float:
    """
    Measure brightness using mean pixel value.
    Optimal range is 130-210 for documents.
    Returns 0.0 (dark or washed out) to 1.0 (optimal).
    """
    mean_val = float(np.mean(gray))
    if _BRIGHTNESS_OPT_LOW <= mean_val <= _BRIGHTNESS_OPT_HIGH:
        return 1.0
    elif mean_val < _BRIGHTNESS_LOW or mean_val > _BRIGHTNESS_HIGH:
        return 0.0
    elif mean_val < _BRIGHTNESS_OPT_LOW:
        return (mean_val - _BRIGHTNESS_LOW) / (_BRIGHTNESS_OPT_LOW - _BRIGHTNESS_LOW)
    else:
        return (_BRIGHTNESS_HIGH - mean_val) / (_BRIGHTNESS_HIGH - _BRIGHTNESS_OPT_HIGH)


def _score_contrast(gray: np.ndarray) -> float:
    """
    Measure contrast using standard deviation of pixel values.
    Higher std = richer contrast between text and background.
    Returns 0.0 (flat) to 1.0 (rich).
    """
    std_val = float(np.std(gray))
    if std_val >= _CONTRAST_RICH_THRESHOLD:
        return 1.0
    elif std_val <= _CONTRAST_FLAT_THRESHOLD:
        return 0.0
    else:
        return (std_val - _CONTRAST_FLAT_THRESHOLD) / (_CONTRAST_RICH_THRESHOLD - _CONTRAST_FLAT_THRESHOLD)


def _score_noise(gray: np.ndarray) -> float:
    """
    Estimate noise by comparing the image to a Gaussian-blurred version.
    Higher difference = more noise.
    Returns 0.0 (very noisy) to 1.0 (clean).
    """
    try:
        gray_u8 = gray.astype(np.uint8)
        blurred = cv2.GaussianBlur(gray_u8, (5, 5), 0)
        diff = np.abs(gray_u8.astype(np.float32) - blurred.astype(np.float32))
        noise_level = float(np.mean(diff))
        # Noise level > 15 = very noisy, < 2 = clean
        if noise_level <= 2.0:
            return 1.0
        elif noise_level >= 15.0:
            return 0.0
        else:
            return 1.0 - (noise_level - 2.0) / (15.0 - 2.0)
    except Exception:
        return 0.7
