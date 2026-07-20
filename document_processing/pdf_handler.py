"""
document_processing/pdf_handler.py
====================================
Thin compatibility wrapper.

The full stitching implementation has moved to:
    document_processing/crops/stitcher.py

This file re-exports get_stitched_base64_document so that all
existing callers (validators, processor.py, app_ui.py) continue
to work with zero changes.
"""
from .crops.stitcher import get_stitched_base64_document

__all__ = ["get_stitched_base64_document"]
