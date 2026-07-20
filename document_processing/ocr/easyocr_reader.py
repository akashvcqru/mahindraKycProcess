"""
ocr/easyocr_reader.py
======================
EasyOCR wrapper that runs on a preprocessed PIL Image.
Returns both flat text AND bounding boxes (detail=1 mode)
so downstream table clustering can use spatial coordinates.

Output format per box:
    {
        "text":       str,       # recognized text
        "bbox":       [[x,y]...],# 4-corner bounding box from EasyOCR
        "x_min":      int,       # left edge
        "x_max":      int,       # right edge
        "y_min":      int,       # top edge
        "y_max":      int,       # bottom edge
        "x_center":   float,
        "y_center":   float,
        "confidence": float      # 0.0 - 1.0
    }
"""
import logging
import numpy as np

# Lazy-load EasyOCR reader (singleton per process — it's heavy to initialize)
_reader = None
_CONFIDENCE_THRESHOLD = 0.35


def _get_reader(languages=None):
    global _reader
    if _reader is None:
        try:
            import easyocr
            langs = languages or ["en"]
            logging.info(f"[easyocr_reader] Initializing EasyOCR reader (languages={langs})...")
            _reader = easyocr.Reader(langs, gpu=False, verbose=False)
            logging.info("[easyocr_reader] EasyOCR reader ready.")
        except ImportError:
            logging.error("[easyocr_reader] easyocr is not installed.")
            raise
    return _reader


def run_easyocr(pil_image, languages=None, min_confidence=_CONFIDENCE_THRESHOLD):
    """
    Run EasyOCR on a preprocessed PIL image and return structured boxes.

    Args:
        pil_image:      PIL.Image (RGB or grayscale)
        languages:      list of language codes, e.g. ["en"]
        min_confidence: Filter out boxes below this confidence (default 0.35)

    Returns:
        tuple: (flat_text: str, boxes: list[dict])
    """
    try:
        reader = _get_reader(languages)

        img_array = np.array(pil_image)
        # EasyOCR expects RGB uint8
        if img_array.ndim == 2:
            img_array = np.stack([img_array] * 3, axis=-1)
        elif img_array.shape[2] == 4:
            img_array = img_array[:, :, :3]

        raw_results = reader.readtext(img_array, detail=1)

        boxes = []
        text_lines = []

        for (bbox, text, confidence) in raw_results:
            if confidence < min_confidence:
                continue
            if not text.strip():
                continue

            xs = [pt[0] for pt in bbox]
            ys = [pt[1] for pt in bbox]
            x_min, x_max = int(min(xs)), int(max(xs))
            y_min, y_max = int(min(ys)), int(max(ys))

            boxes.append({
                "text":       text.strip(),
                "bbox":       bbox,
                "x_min":      x_min,
                "x_max":      x_max,
                "y_min":      y_min,
                "y_max":      y_max,
                "x_center":   (x_min + x_max) / 2,
                "y_center":   (y_min + y_max) / 2,
                "confidence": round(confidence, 4),
            })
            text_lines.append(text.strip())

        flat_text = "\n".join(text_lines)
        logging.info(f"[easyocr_reader] Extracted {len(boxes)} text boxes (conf >= {min_confidence})")
        return flat_text, boxes

    except Exception as e:
        logging.error(f"[easyocr_reader] OCR failed: {e}")
        return "", []
