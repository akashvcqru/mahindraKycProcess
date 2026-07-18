"""
reader_base.py
==============
Shared utilities used by ALL python readers.

Provides:
  - extract_pdf_text()   → raw text from a PDF/image
  - is_text_based()      → True if PDF has enough embedded text
  - line_fraction()      → approximate vertical position (0–1) of a line

Each reader returns a dict like:
  {
      "field_name": {"text": "...", "line": N, "source": "python"},
      ...
  }
Fields that could NOT be extracted are left out of the dict (caller treats
missing keys as "need AI").
"""

import logging
import os
import re

import fitz  # PyMuPDF


# Minimum characters of extracted text to consider a PDF "text-based"
_TEXT_MIN_CHARS = 80


def extract_pdf_text(pdf_path: str) -> str:
    """
    Return the full plain-text content of a PDF (all pages joined).
    Returns empty string if the file cannot be read or has no embedded text.
    """
    if not os.path.exists(pdf_path):
        return ""
    try:
        if pdf_path.lower().endswith(".pdf"):
            doc = fitz.open(pdf_path)
            pages_text = []
            for page in doc:
                pages_text.append(page.get_text("text"))
            return "\n".join(pages_text)
        else:
            return ""
    except Exception as exc:
        logging.warning(f"[reader_base] Could not extract text from {pdf_path}: {exc}")
        return ""


def is_text_based(pdf_path: str) -> bool:
    """
    Returns True if the PDF has enough embedded text to attempt Python extraction.
    """
    text = extract_pdf_text(pdf_path)
    return len(text.strip()) >= _TEXT_MIN_CHARS


def _field(text_value: str, line_no: int = 0) -> dict:
    """Build a standardised field dict returned by all readers."""
    return {
        "text": text_value.strip(),
        "line": line_no,
        "source": "python",
    }


def first_match(pattern: str, text: str, flags=re.IGNORECASE) -> str | None:
    """Return the first captured group of *pattern* in *text*, or None."""
    m = re.search(pattern, text, flags)
    if m:
        return m.group(1).strip()
    return None


def line_of(pattern: str, lines: list[str], flags=re.IGNORECASE) -> int:
    """Return the 1-based line number where *pattern* first matches, or 0."""
    for i, ln in enumerate(lines, 1):
        if re.search(pattern, ln, flags):
            return i
    return 0
