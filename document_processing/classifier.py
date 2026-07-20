"""
document_processing/classifier.py
====================================
Centralized document type classifier.

Replaces the inline classify_document() in welcome_scheme/processor.py
with a scored, extensible classifier that handles all document types:

    INVOICE    — Tax Invoice / GST Invoice
    LEDGER     — Ledger Account / Statement of Account
    DISCLAIMER — Customer Disclaimer
    GST        — GST Registration Certificate
    PAN        — PAN Card
    AADHAAR    — Aadhaar Card
    COD        — Certificate of Deposit / OEM Certificate
    RC         — Vehicle Registration Certificate
    DL         — Driving Licence

Returns a result dict with type + confidence so callers can apply
UNKNOWN routing when confidence is low.

Usage:
    from document_processing.classifier import classify_document
    result = classify_document("/path/to/file.pdf")
    # {"type": "INVOICE", "confidence": 0.92, "method": "filename"}
"""

import logging
import os
import re
from typing import Optional


# ── Keyword tables ─────────────────────────────────────────────────────────────
# Each doc type has filename prefixes, filename keywords, and content keywords.
# Content keywords are used only when filename checks are inconclusive.

_TYPES: dict[str, dict] = {
    "INVOICE": {
        "fn_prefixes":  ("INV",),
        "fn_keywords":  ("INVOICE", "TAX INV", "GST INV", "TAX INVOICE", "GST INVOICE"),
        "content":      ("TAX INVOICE", "GST INVOICE", "RETAIL INVOICE", "INVOICE NO", "INVOICE NUMBER",
                         "BILL NO", "BILL NUMBER", "TAXABLE VALUE"),
        "weight":       1.0,
    },
    "LEDGER": {
        "fn_prefixes":  ("LDGR", "LES", "L-", "LGR", "LDR", "LDG", "LR-", "LR"),
        "fn_keywords":  ("LEDGER", "STMT", "STATEMENT"),
        "content":      ("STATEMENT OF ACCOUNT", "LEDGER ACCOUNT", "JOURNAL ENTRY",
                         "OPENING BALANCE", "CLOSING BALANCE", "STATEMENT OF A/C",
                         "ACCOUNT STATEMENT", "LEDGER STATEMENT", "PARTICULARS"),
        "weight":       1.0,
    },
    "DISCLAIMER": {
        "fn_prefixes":  ("DIS", "DSC", "CD-", "DS", "MFC", "FC", "CERT",
                         "FORM", "CUST", "DECL", "DIC", "DEC"),
        "fn_keywords":  ("DISCLAIMER", "DESCLAIMER"),
        "content":      ("CUSTOMER DISCLAIMER", "DISCLAIMER FOR WELCOME",
                         "I CONFIRM THAT I HAVE AVAILED", "WELCOME BONUS OF RS",
                         "DISCLAIMER", "UNDERTAKING"),
        "weight":       1.0,
    },
    "GST": {
        "fn_prefixes":  ("GST",),
        "fn_keywords":  ("GST CERTIFICATE", "GST REG", "GSTIN"),
        "content":      ("GOODS AND SERVICES TAX", "CERTIFICATE OF REGISTRATION",
                         "GSTIN", "GST IDENTIFICATION NUMBER"),
        "weight":       0.9,
    },
    "PAN": {
        "fn_prefixes":  ("PAN",),
        "fn_keywords":  ("PAN CARD", "PAN"),
        "content":      ("PERMANENT ACCOUNT NUMBER", "INCOME TAX DEPARTMENT",
                         "PAN NUMBER"),
        "weight":       0.9,
    },
    "AADHAAR": {
        "fn_prefixes":  ("AAD", "AADH", "ADH"),
        "fn_keywords":  ("AADHAAR", "AADHAR", "ADHAAR"),
        "content":      ("AADHAAR", "UNIQUE IDENTIFICATION", "UIDAI"),
        "weight":       0.9,
    },
    "COD": {
        "fn_prefixes":  ("COD", "ELV", "CERT"),
        "fn_keywords":  ("CERTIFICATE OF DEPOSIT", "OEM CERTIFICATE", "ELV CERTIFICATE"),
        "content":      ("CERTIFICATE OF DEPOSIT", "END OF LIFE VEHICLE",
                         "SCRAP CERTIFICATE"),
        "weight":       0.85,
    },
    "OEM": {
        "fn_prefixes":  ("OEM",),
        "fn_keywords":  ("VAHAN SCREEN", "VAHAN", "VAHON", "SCREENSHOT", "SCREEN SHORT",
                         "OEM SCRAPPING", "OEM SCRAPPING INCENTIVE"),
        "content":      ("OEM SCRAPPING", "OEM INCENTIVE", "DETAILS OF CDS"),
        "weight":       0.9,
    },
    "RC": {
        "fn_prefixes":  ("RC",),
        "fn_keywords":  ("RC BOOK", "REGISTRATION CERTIFICATE", "VEHICLE RC"),
        "content":      ("REGISTRATION CERTIFICATE", "VEHICLE REGISTRATION",
                         "REGISTERING AUTHORITY"),
        "weight":       0.85,
    },
    "DL": {
        "fn_prefixes":  ("DL",),
        "fn_keywords":  ("DRIVING LICENCE", "DRIVING LICENSE", "DL"),
        "content":      ("DRIVING LICENCE", "DRIVING LICENSE",
                         "TRANSPORT DEPARTMENT"),
        "weight":       0.80,
    },
}

# Confidence given when the match is from filename vs content
_CONF_FN_PREFIX   = 0.95
_CONF_FN_KEYWORD  = 0.90
_CONF_CONTENT     = 0.75

# Minimum confidence to return a result (else return type=None)
_MIN_CONFIDENCE   = 0.50


def classify_document(file_path: str, extracted_text: Optional[str] = None) -> dict:
    """
    Classify a document file by type using filename heuristics and content analysis.

    Args:
        file_path:      Absolute path to the PDF or image file
        extracted_text: Pre-extracted text (optional). If None, text will be
                        extracted automatically for content-based classification.

    Returns:
        dict: {
            "type":       "INVOICE" | "LEDGER" | "DISCLAIMER" | "GST" | "PAN" |
                          "AADHAAR" | "COD" | "RC" | "DL" | None,
            "confidence": float (0.0-1.0),
            "method":     "fn_prefix" | "fn_keyword" | "content" | "none",
        }
    """
    filename = os.path.basename(file_path).upper()
    filename_noext = os.path.splitext(filename)[0]

    # ── 1. Filename prefix checks (highest confidence) ─────────────────────────
    for doc_type, cfg in _TYPES.items():
        for prefix in cfg["fn_prefixes"]:
            if (filename_noext.startswith(prefix) or
                    f" {prefix}" in filename_noext or
                    f"-{prefix}" in filename_noext or
                    f"_{prefix}" in filename_noext):
                logging.info(
                    f"[classifier] {os.path.basename(file_path)} → {doc_type} "
                    f"(fn_prefix='{prefix}', conf={_CONF_FN_PREFIX})"
                )
                return {
                    "type":       doc_type,
                    "confidence": _CONF_FN_PREFIX * cfg["weight"],
                    "method":     "fn_prefix",
                }

    # ── 2. Filename keyword checks ─────────────────────────────────────────────
    for doc_type, cfg in _TYPES.items():
        for keyword in cfg["fn_keywords"]:
            if keyword in filename:
                logging.info(
                    f"[classifier] {os.path.basename(file_path)} → {doc_type} "
                    f"(fn_keyword='{keyword}', conf={_CONF_FN_KEYWORD})"
                )
                return {
                    "type":       doc_type,
                    "confidence": _CONF_FN_KEYWORD * cfg["weight"],
                    "method":     "fn_keyword",
                }

    # ── 3. Content-based classification ────────────────────────────────────────
    text = _get_text(file_path, extracted_text)
    if not text:
        logging.warning(f"[classifier] Could not extract text from {file_path}. Type unknown.")
        return {"type": None, "confidence": 0.0, "method": "none"}

    text_upper = text.upper()

    # Score each type by how many of its content keywords appear in the text
    scores: dict[str, float] = {}
    for doc_type, cfg in _TYPES.items():
        hits = sum(1 for kw in cfg["content"] if kw in text_upper)
        if hits > 0:
            # Normalize: more hits = higher confidence, capped at _CONF_CONTENT
            conf = min(_CONF_CONTENT, _CONF_CONTENT * (hits / len(cfg["content"])) * 2)
            scores[doc_type] = conf * cfg["weight"]

    if scores:
        best_type = max(scores, key=scores.__getitem__)
        best_conf = scores[best_type]
        if best_conf >= _MIN_CONFIDENCE:
            logging.info(
                f"[classifier] {os.path.basename(file_path)} → {best_type} "
                f"(content match, conf={best_conf:.2f})"
            )
            return {
                "type":       best_type,
                "confidence": round(best_conf, 3),
                "method":     "content",
            }

    logging.warning(f"[classifier] Could not classify {os.path.basename(file_path)}")
    return {"type": None, "confidence": 0.0, "method": "none"}


def _get_text(file_path: str, extracted_text: Optional[str] = None) -> str:
    """Get or extract text for content classification."""
    if extracted_text:
        return extracted_text

    # Check cache first
    try:
        parent = os.path.basename(os.path.dirname(file_path))
        fname  = os.path.basename(file_path)
        cache_path = os.path.join("scratch", "ocr_txt", f"{parent}_{fname}.txt")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = f.read()
            if len(cached.strip()) >= 20:
                return cached
    except Exception:
        pass

    # Try fast digital extraction via PyMuPDF
    try:
        import fitz
        doc  = fitz.open(file_path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        if len(text.strip()) >= 20:
            return text
    except Exception:
        pass

    # Lightweight EasyOCR on first page only (for classification, not extraction)
    try:
        import fitz
        import easyocr
        import numpy as np
        from PIL import Image
        import io

        doc = fitz.open(file_path)
        pix = doc[0].get_pixmap(dpi=150)
        doc.close()
        pil_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        reader  = easyocr.Reader(["en"], gpu=False, verbose=False)
        results = reader.readtext(np.array(pil_img), detail=0)
        return " ".join(results)
    except Exception as e:
        logging.warning(f"[classifier] OCR fallback failed for {file_path}: {e}")
        return ""
