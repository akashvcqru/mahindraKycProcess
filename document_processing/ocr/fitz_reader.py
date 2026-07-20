"""
ocr/fitz_reader.py
===================
Uses PyMuPDF (fitz) to attempt fast digital text extraction
from a PDF page before falling back to EasyOCR.

Returns:
    (text: str, is_digital: bool)
    is_digital = True  → meaningful text found, skip OCR
    is_digital = False → page is a scan, use OCR
"""
import logging

# Minimum character count to consider a page as "digital text"
_DIGITAL_TEXT_THRESHOLD = 30


def extract_page_text_fitz(pdf_path: str, page_num: int = 0):
    """
    Extract text from a single PDF page using PyMuPDF.

    Args:
        pdf_path: Absolute path to the PDF file
        page_num: Zero-indexed page number

    Returns:
        tuple: (text: str, is_digital: bool)
    """
    try:
        import fitz
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            doc.close()
            return "", False

        page = doc.load_page(page_num)
        text = page.get_text("text") or ""
        doc.close()

        is_digital = len(text.strip()) >= _DIGITAL_TEXT_THRESHOLD
        if is_digital:
            logging.info(f"[fitz_reader] Page {page_num}: digital text found ({len(text.strip())} chars), skipping OCR")
        else:
            logging.info(f"[fitz_reader] Page {page_num}: no digital text ({len(text.strip())} chars), OCR needed")

        return text, is_digital

    except Exception as e:
        logging.error(f"[fitz_reader] Error reading page {page_num} from {pdf_path}: {e}")
        return "", False


def render_page_to_pil(pdf_path: str, page_num: int = 0, dpi: int = 200):
    """
    Render a PDF page to a PIL Image at the given DPI.
    Used when EasyOCR fallback is needed.

    Args:
        pdf_path: Absolute path to the PDF file
        page_num: Zero-indexed page number
        dpi:      Render resolution (200 DPI is good balance of speed/quality for OCR)

    Returns:
        PIL.Image or None
    """
    try:
        import fitz
        from PIL import Image
        import io

        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            doc.close()
            return None

        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=matrix)
        img_data = pix.tobytes("png")
        doc.close()

        return Image.open(io.BytesIO(img_data))

    except Exception as e:
        logging.error(f"[fitz_reader] Error rendering page {page_num}: {e}")
        return None


def count_pages(pdf_path: str) -> int:
    """Return total page count for a PDF."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        n = len(doc)
        doc.close()
        return n
    except Exception:
        return 0
