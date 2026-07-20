"""
document_processing/table
==========================
Spatial clustering: turns raw EasyOCR bounding boxes into
structured table rows and columns.
Entry point: table_builder.build_table(boxes, doc_type) -> list[dict]
"""
from .table_builder import build_table

__all__ = ["build_table"]
