"""
preprocessing/pipeline.py
==========================
Single entry point for the full preprocessing chain.
Call preprocess_page(pil_image) before feeding to EasyOCR.

Pipeline order (each step builds on the last):
  1. Image Quality Score   (image_quality.score_image_quality)  ← NEW
  2. Watermark suppression (contrast.suppress_watermark)
  3. Contrast enhancement  (contrast.enhance_contrast with CLAHE)
  4. Deskew                (deskew.deskew_image)

Returns:
  Tuple[PIL.Image, dict]: (cleaned_image, quality_result)
  The quality_result dict includes:
    - score:       0-100 overall quality score
    - low_quality: True if score < 40 (OCR results unreliable)
    - reason:      Human-readable explanation if low_quality
"""
import logging
from .deskew import deskew_image
from .contrast import enhance_contrast, suppress_watermark
from .image_quality import score_image_quality


def preprocess_page(pil_image, deskew=True, suppress_wm=True, enhance=True,
                    score_quality=True):
    """
    Run the full preprocessing pipeline on a PIL image page.

    Args:
        pil_image:     PIL.Image — raw page render from fitz or image file
        deskew:        bool — apply rotation correction (default True)
        suppress_wm:   bool — suppress light watermarks, preserve colored stamps (default True)
        enhance:       bool — CLAHE contrast enhancement (default True)
        score_quality: bool — calculate image quality score before processing (default True)

    Returns:
        Tuple[PIL.Image, dict]:
            PIL.Image — Preprocessed image ready for EasyOCR
            dict      — Quality assessment result from score_image_quality()
                        Has keys: score, blur_score, brightness_score,
                                  contrast_score, noise_score, low_quality, reason
    """
    img = pil_image
    quality_result = {"score": 100, "low_quality": False, "reason": ""}

    # Step 0: Score image quality on the raw (unprocessed) image
    if score_quality:
        quality_result = score_image_quality(pil_image)
        if quality_result["low_quality"]:
            logging.warning(
                f"[preprocess] Low quality scan detected "
                f"(score={quality_result['score']:.1f}/100): {quality_result['reason']}"
            )

    # Step 1: Suppress watermarks (background-aware, preserves colored stamps)
    if suppress_wm:
        img = suppress_watermark(img)
        logging.debug("[preprocess] Watermark suppression applied")

    # Step 2: CLAHE contrast enhancement
    if enhance:
        img = enhance_contrast(img, method="clahe")
        logging.debug("[preprocess] CLAHE contrast enhancement applied")

    # Step 3: Deskew
    if deskew:
        img = deskew_image(img)
        logging.debug("[preprocess] Deskew applied")

    return img, quality_result
