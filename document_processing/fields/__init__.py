"""
document_processing/fields
============================
RapidFuzz-based fuzzy label matching against canonical field name lists.
Entry point: fuzzy_matcher.match_label(ocr_text, doc_type) -> (best_field, score)
"""
from .fuzzy_matcher import match_label, match_label_list

__all__ = ["match_label", "match_label_list"]
