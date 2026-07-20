"""
document_processing/ocr
========================
OCR engine that tries PyMuPDF (fitz) first on a per-page basis,
then falls back to EasyOCR on the preprocessed image.
Entry point: engine.extract_page(pdf_path, page_num) -> (text, boxes, is_digital)
"""
from .engine import extract_page, extract_all_pages

__all__ = ["extract_page", "extract_all_pages"]
