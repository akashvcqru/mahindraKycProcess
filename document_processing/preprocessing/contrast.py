"""
preprocessing/contrast.py
==========================
Contrast enhancement and watermark/stamp suppression using OpenCV.
Uses CLAHE (Contrast Limited Adaptive Histogram Equalization) +
adaptive thresholding to improve OCR readability.
"""
import logging
import numpy as np

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


def enhance_contrast(pil_image, method="clahe"):
    """
    Enhance contrast of a scanned document page to improve OCR accuracy.
    Suppresses low-contrast watermarks (e.g. Mahindra logo) and circular stamps
    that bleed into tabular text rows.

    Args:
        pil_image: PIL.Image (RGB)
        method: "clahe" (default adaptive) or "threshold" (hard binary)

    Returns:
        PIL.Image: Contrast-enhanced image (RGB)
    """
    if not _CV2_AVAILABLE:
        return pil_image

    try:
        from PIL import Image

        img_array = np.array(pil_image.convert("RGB"))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        if method == "threshold":
            # Hard adaptive threshold — best for dense tabular text
            processed = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=15,
                C=10
            )
            # Return as RGB (3-channel) for compatibility
            result = cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB)

        else:
            # CLAHE — best general-purpose enhancement
            # Reduces stamp/watermark bleed while keeping text sharp
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)

            # Mild denoising to remove scanner grain
            denoised = cv2.fastNlMeansDenoising(enhanced, h=10)

            result = cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)

        return Image.fromarray(result)

    except Exception as e:
        logging.warning(f"[contrast] Error enhancing contrast: {e}. Returning original.")
        return pil_image


def suppress_watermark(pil_image):
    """
    Suppress light watermarks (ghosted logos) using background-aware adaptive
    thresholding that preserves colored ink (blue/purple dealer stamps).

    Strategy:
    1. Detect the background median from the brightest pixel region
    2. Only suppress pixels within ±20 gray units of the background median
    3. Explicitly preserve pixels with strong color saturation (stamps/seals
       are typically blue or purple — these are NOT watermarks)

    This replaces the old fixed >175 threshold that was erasing dealer stamps.

    Args:
        pil_image: PIL.Image (RGB)

    Returns:
        PIL.Image: Watermark-suppressed image (RGB)
    """
    if not _CV2_AVAILABLE:
        return pil_image

    try:
        from PIL import Image

        img_array = np.array(pil_image.convert("RGB"))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        # ── Step 1: Detect background color using median of bright pixels ──────
        # Background pixels are typically the top 15% brightest
        bright_threshold = np.percentile(gray, 85)
        bright_pixels = gray[gray >= bright_threshold]
        background_median = float(np.median(bright_pixels)) if len(bright_pixels) > 0 else 220.0

        # Suppress range: background_median ± 20 (tighter than old fixed >175)
        suppress_low  = max(160, background_median - 20)
        suppress_high = 255

        # ── Step 2: Identify watermark pixels (bright grayscale, in suppress range) ─
        watermark_mask = (gray >= suppress_low) & (gray <= suppress_high)

        # ── Step 3: Exclude colored pixels (stamps have color saturation) ─────
        # Convert to HSV to detect colored ink
        img_hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
        saturation = img_hsv[:, :, 1]   # S channel: 0 = grey, 255 = vivid color

        # Blue/purple stamps: H roughly 100-160, S > 40 (they are colored)
        hue = img_hsv[:, :, 0]
        is_blue_purple = ((hue >= 100) & (hue <= 160) & (saturation > 40))

        # Any pixel with significant color saturation (S > 35) is NOT watermark
        is_colored = saturation > 35

        # Final suppress mask: watermark AND not colored
        final_mask = watermark_mask & ~is_colored & ~is_blue_purple

        # ── Step 4: Apply suppression ─────────────────────────────────────────
        img_array[final_mask] = [255, 255, 255]

        suppressed_count = int(np.sum(final_mask))
        logging.debug(
            f"[contrast] Watermark suppression: background_median={background_median:.0f}, "
            f"suppress_range=[{suppress_low:.0f}, 255], pixels_suppressed={suppressed_count}"
        )

        return Image.fromarray(img_array)

    except Exception as e:
        logging.warning(f"[contrast] Error suppressing watermark: {e}. Returning original.")
        return pil_image
