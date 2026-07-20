"""
ocr/engine.py
=============
Orchestrator: try PyMuPDF fitz first per page.
If the page has no digital text (it's a scan), preprocess it
with OpenCV and run EasyOCR.

Main entry points:
    extract_page(pdf_path, page_num) -> PageResult
    extract_all_pages(pdf_path)      -> list[PageResult]

PageResult is a dict:
    {
        "page":          int,   # zero-indexed page number
        "text":          str,   # flat extracted text
        "boxes":         list,  # EasyOCR bounding boxes (empty if digital)
        "is_digital":    bool,  # True = came from fitz, False = came from EasyOCR
        "image_quality": dict,  # quality assessment from score_image_quality()
                                #   keys: score, low_quality, blur_score, etc.
    }
"""
import logging
from .fitz_reader import extract_page_text_fitz, render_page_to_pil, count_pages
from .easyocr_reader import run_easyocr
from ..preprocessing.pipeline import preprocess_page


def extract_page(pdf_path: str, page_num: int = 0, ocr_dpi: int = 200) -> dict:
    """
    Extract text and bounding boxes from a single PDF page.
    Uses fitz first; falls back to EasyOCR if the page is scanned.

    Args:
        pdf_path: Path to PDF
        page_num: Zero-indexed page
        ocr_dpi:  DPI for page rendering when OCR is needed (200 is good for speed)

    Returns:
        dict: PageResult with keys page, text, boxes, is_digital
    """
    # Step 1: Try fast digital text extraction
    text, is_digital = extract_page_text_fitz(pdf_path, page_num)

    if is_digital:
        return {
            "page":          page_num,
            "text":          text,
            "boxes":         [],
            "is_digital":    True,
            "image_quality": {"score": 100, "low_quality": False, "reason": "digital PDF"},
        }

    # Step 2: Render page to PIL for OCR
    pil_image = render_page_to_pil(pdf_path, page_num, dpi=ocr_dpi)
    if pil_image is None:
        logging.error(f"[engine] Could not render page {page_num} from {pdf_path}")
        return {
            "page": page_num, "text": "", "boxes": [], "is_digital": False,
            "image_quality": {"score": 0, "low_quality": True, "reason": "render failed"},
        }

    # Step 3: Preprocess (quality score + deskew + contrast boost + watermark suppression)
    # preprocess_page now returns (cleaned_image, quality_result)
    cleaned_image, quality_result = preprocess_page(pil_image)

    if quality_result.get("low_quality"):
        logging.warning(
            f"[engine] Page {page_num} has low quality score={quality_result['score']:.1f}/100. "
            f"OCR results may be unreliable. Reason: {quality_result.get('reason', '')}"
        )

    # Step 4: Run EasyOCR on the clean image
    flat_text, boxes = run_easyocr(cleaned_image)

    return {
        "page":          page_num,
        "text":          flat_text,
        "boxes":         boxes,
        "is_digital":    False,
        "image_quality": quality_result,
    }


def extract_all_pages(pdf_path: str, ocr_dpi: int = 200) -> list:
    """
    Extract text and boxes from all pages in a PDF.

    Args:
        pdf_path: Path to PDF
        ocr_dpi:  DPI for page rendering when OCR is needed

    Returns:
        list[PageResult]: One result per page
    """
    n = count_pages(pdf_path)
    if n == 0:
        logging.warning(f"[engine] No pages found in {pdf_path}")
        return []

    results = []
    for page_num in range(n):
        result = extract_page(pdf_path, page_num, ocr_dpi)
        results.append(result)

    combined_text = "\n".join(r["text"] for r in results)
    logging.info(f"[engine] Processed {n} page(s) from {pdf_path} | Total chars: {len(combined_text)}")
    return results


def extract_full_text(pdf_path: str, ocr_dpi: int = 200) -> str:
    """
    Convenience function: returns a single flat text string for all pages.
    Use this when you only need text (not bounding boxes).
    """
    results = extract_all_pages(pdf_path, ocr_dpi)
    return "\n".join(r["text"] for r in results)
