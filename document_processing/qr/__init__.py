"""
document_processing/qr
========================
QR code and barcode decoding using OpenCV QRCodeDetector.
Entry point: qr_decoder.decode_qr(pil_image) -> list[str]
"""
from .qr_decoder import decode_qr

__all__ = ["decode_qr"]
