"""
document_processing/preprocessing
==================================
OpenCV-based image preprocessing before OCR.
Entry point: pipeline.preprocess_page(pil_image) -> pil_image
"""
from .pipeline import preprocess_page

__all__ = ["preprocess_page"]
