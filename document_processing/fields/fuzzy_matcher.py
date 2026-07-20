"""
fields/fuzzy_matcher.py
========================
RapidFuzz-based fuzzy label matching.
Corrects OCR label misreads by finding the closest canonical field name.

Usage:
    from document_processing.fields import match_label
    field, score = match_label("Vch No.", doc_type="ledger")
    # → ("Vch No", 96.2)

    fields = match_label_list(["CGST/SAC", "Taxible Value"], doc_type="invoice")
    # → [("CGST Rate", 78.0), ("Taxable Value", 91.5)]
"""
import logging

try:
    from rapidfuzz import fuzz, process as rfprocess
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False
    logging.warning("[fuzzy_matcher] rapidfuzz not installed. Field matching will use exact comparison only.")

from .canonical_ledger import LEDGER_FIELDS
from .canonical_invoice import INVOICE_FIELDS
from .canonical_disclaimer import DISCLAIMER_FIELDS

_FIELD_MAP = {
    "ledger":     LEDGER_FIELDS,
    "invoice":    INVOICE_FIELDS,
    "disclaimer": DISCLAIMER_FIELDS,
}

# Minimum score to consider a match valid (0-100)
_MIN_SCORE = 60


def _get_field_list(doc_type: str) -> list:
    return _FIELD_MAP.get(doc_type, LEDGER_FIELDS + INVOICE_FIELDS + DISCLAIMER_FIELDS)


def match_label(ocr_text: str, doc_type: str = "ledger",
                min_score: int = _MIN_SCORE) -> tuple:
    """
    Match an OCR'd label string against the canonical field list for doc_type.

    Args:
        ocr_text:  Raw OCR'd label text (may have typos/misreads)
        doc_type:  "ledger", "invoice", or "disclaimer"
        min_score: Minimum fuzzy score to return a match (default 60)

    Returns:
        tuple: (best_field: str, score: float)
               Returns (ocr_text, 0.0) if no match above min_score.
    """
    if not ocr_text or not ocr_text.strip():
        return ocr_text, 0.0

    field_list = _get_field_list(doc_type)

    if not _RAPIDFUZZ_AVAILABLE:
        # Exact match fallback
        text_upper = ocr_text.upper()
        for field in field_list:
            if field.upper() == text_upper:
                return field, 100.0
        return ocr_text, 0.0

    result = rfprocess.extractOne(
        ocr_text,
        field_list,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=min_score,
    )

    if result:
        best_field, score, _ = result
        logging.debug(f"[fuzzy_matcher] '{ocr_text}' → '{best_field}' (score={score:.1f})")
        return best_field, score

    logging.debug(f"[fuzzy_matcher] No match for '{ocr_text}' (all scores < {min_score})")
    return ocr_text, 0.0


def match_label_list(ocr_texts: list, doc_type: str = "ledger",
                     min_score: int = _MIN_SCORE) -> list:
    """
    Match a list of OCR'd label strings.

    Args:
        ocr_texts: list of raw OCR label strings
        doc_type:  "ledger", "invoice", or "disclaimer"
        min_score: Minimum fuzzy score

    Returns:
        list[tuple]: [(best_field, score), ...] in same order as input
    """
    return [match_label(t, doc_type, min_score) for t in ocr_texts]
