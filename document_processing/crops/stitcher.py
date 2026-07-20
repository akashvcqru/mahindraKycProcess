"""
crops/stitcher.py
=================
Vertically stitches multi-page PDF or image files into a single
high-quality JPEG and returns it as a base64 string.

Moved from document_processing/pdf_handler.py — no behavior change.
All callers of pdf_handler.get_stitched_base64_document() still work
because pdf_handler.py imports from here.
"""
import os
import base64
import io
import logging

from PIL import Image


def get_stitched_base64_document(file_path: str, dpi: int = 300,
                                  quality: int = 85) -> str | None:
    """
    Convert a multi-page PDF or image file into a single vertically stitched
    optimized JPEG base64 string.

    Args:
        file_path: Absolute path to PDF or image file
        dpi:       Render resolution for PDF pages (default 300 for high quality)
        quality:   JPEG output quality 1-95 (default 85)

    Returns:
        str: base64-encoded JPEG string, or None on failure
    """
    if not file_path or not os.path.exists(file_path):
        logging.warning(f"[stitcher] File not found: {file_path}")
        return None

    ext = os.path.splitext(file_path.lower())[1]
    images = []

    try:
        if ext == ".pdf":
            import fitz
            doc = fitz.open(file_path)
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=matrix)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
            doc.close()

        elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"):
            img = Image.open(file_path)
            img.load()
            images.append(img)

        else:
            logging.warning(f"[stitcher] Unsupported file format: {ext}")
            return None

        if not images:
            return None

        # Stitch images vertically
        max_width   = max(img.width for img in images)
        total_height = sum(img.height for img in images)

        stitched = Image.new("RGBA", (max_width, total_height), (255, 255, 255, 0))
        y_offset = 0
        for img in images:
            stitched.paste(img, (0, y_offset))
            y_offset += img.height

        # Convert to RGB JPEG
        buffered = io.BytesIO()
        if (stitched.mode in ("RGBA", "LA") or
                (stitched.mode == "P" and "transparency" in stitched.info)):
            bg = Image.new("RGB", stitched.size, (255, 255, 255))
            bg.paste(stitched, mask=stitched.split()[3])
            stitched = bg
        else:
            stitched = stitched.convert("RGB")

        stitched.save(buffered, format="JPEG", quality=quality, optimize=True)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        logging.info(
            f"[stitcher] Stitched {os.path.basename(file_path)}: "
            f"{len(images)} page(s), {len(img_str)//1024}KB base64"
        )
        return img_str

    except Exception as e:
        logging.error(f"[stitcher] Error processing {file_path}: {e}")
        return None
