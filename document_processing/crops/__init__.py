"""
document_processing/crops
===========================
Pillow-based page stitching and evidence region cropping.
- stitcher.get_stitched_base64_document(file_path) -> base64 str
- region_cropper.crop_region(pil_image, top, left, bottom, right) -> base64 str
"""
from .stitcher import get_stitched_base64_document
from .region_cropper import crop_region

__all__ = ["get_stitched_base64_document", "crop_region"]
