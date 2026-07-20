"""
document_processing/signature
===============================
Stamp and handwritten signature presence detection using
OpenCV contour and blob analysis.
Entry point: detector.detect_signature_and_stamp(pil_image, crop_region) -> dict
"""
from .detector import detect_signature_and_stamp

__all__ = ["detect_signature_and_stamp"]
