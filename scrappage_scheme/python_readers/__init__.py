"""
python_readers/__init__.py
==========================
Expose each reader module by document type for convenience.
"""

from .reader_base       import extract_pdf_text, is_text_based
from .reader_cod        import try_extract_cod_fields
from .reader_oem        import try_extract_oem_fields
from .reader_ledger     import try_extract_ledger_fields
from .reader_invoice    import try_extract_invoice_fields
from .reader_disclaimer import try_extract_disclaimer_fields

__all__ = [
    "extract_pdf_text",
    "is_text_based",
    "try_extract_cod_fields",
    "try_extract_oem_fields",
    "try_extract_ledger_fields",
    "try_extract_invoice_fields",
    "try_extract_disclaimer_fields",
]
