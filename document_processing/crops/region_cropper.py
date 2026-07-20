"""
crops/region_cropper.py
========================
Pillow-based evidence region cropping.

Once the table/row cluster has identified row boundaries (e.g. the
closing balance row, the stamp area, the signature line), use this
module to crop those regions and return them as base64 for display
in the dashboard's Visual Confirmation panel.
"""
import base64
import io
import logging

from PIL import Image


def crop_region(pil_image, top: float, left: float,
                bottom: float, right: float,
                format: str = "JPEG", quality: int = 90) -> str | None:
    """
    Crop a rectangular region from a PIL Image and return as base64.

    Args:
        pil_image:          PIL.Image (RGB)
        top, left, bottom, right: Region boundaries as fractions 0.0-1.0
        format:             Output format — "JPEG" or "PNG"
        quality:            JPEG quality (ignored for PNG)

    Returns:
        str: base64-encoded image string, or None on failure
    """
    try:
        w, h = pil_image.size
        box = (
            int(left * w),
            int(top * h),
            int(right * w),
            int(bottom * h),
        )
        cropped = pil_image.crop(box)

        if cropped.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", cropped.size, (255, 255, 255))
            bg.paste(cropped, mask=cropped.split()[-1])
            cropped = bg
        elif cropped.mode != "RGB":
            cropped = cropped.convert("RGB")

        buffered = io.BytesIO()
        if format.upper() == "PNG":
            cropped.save(buffered, format="PNG")
        else:
            cropped.save(buffered, format="JPEG", quality=quality, optimize=True)

        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    except Exception as e:
        logging.error(f"[region_cropper] Error cropping region: {e}")
        return None


def crop_region_px(pil_image, x1: int, y1: int,
                   x2: int, y2: int,
                   format: str = "JPEG", quality: int = 90) -> str | None:
    """
    Crop a region using absolute pixel coordinates and return as base64.

    Args:
        pil_image: PIL.Image
        x1, y1:   Top-left corner (pixels)
        x2, y2:   Bottom-right corner (pixels)
        format:    "JPEG" or "PNG"
        quality:   JPEG quality

    Returns:
        str: base64-encoded image string, or None on failure
    """
    try:
        cropped = pil_image.crop((x1, y1, x2, y2))
        if cropped.mode not in ("RGB",):
            cropped = cropped.convert("RGB")

        buffered = io.BytesIO()
        if format.upper() == "PNG":
            cropped.save(buffered, format="PNG")
        else:
            cropped.save(buffered, format="JPEG", quality=quality, optimize=True)

        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    except Exception as e:
        logging.error(f"[region_cropper] Error cropping px region: {e}")
        return None
