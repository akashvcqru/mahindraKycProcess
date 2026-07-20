"""
table/table_builder.py
=======================
Entry point: converts raw EasyOCR boxes into a structured table
(list of row dicts) for a given document type.

Usage:
    from document_processing.table import build_table
    rows = build_table(boxes, doc_type="ledger", page_width=1654)

Returns:
    list[dict]: One dict per table row, with column names as keys.
"""
import logging
from .row_cluster import cluster_rows
from .col_binner_ledger import bin_row_to_ledger_columns
from .col_binner_invoice import bin_row_to_invoice_columns

SUPPORTED_DOC_TYPES = ("ledger", "invoice", "disclaimer")


def build_table(boxes: list, doc_type: str, page_width: int,
                y_tolerance: int = 8) -> list:
    """
    Build a structured table from EasyOCR bounding boxes.

    Args:
        boxes:       list of box dicts from easyocr_reader.run_easyocr()
        doc_type:    "ledger" or "invoice" (disclaimer returns flat rows only)
        page_width:  width of the page image in pixels (needed for column binning)
        y_tolerance: pixel tolerance for row grouping (default 8)

    Returns:
        list[dict]: Structured rows. Each row has column names as keys.
                    For disclaimer, rows have a single "text" key.
    """
    if not boxes:
        logging.warning(f"[table_builder] No boxes provided for doc_type={doc_type}")
        return []

    # Step 1: Group boxes into rows by Y proximity
    rows = cluster_rows(boxes, y_tolerance=y_tolerance)
    logging.info(f"[table_builder] {len(rows)} rows clustered for doc_type={doc_type}")

    structured = []

    if doc_type == "ledger":
        for row_boxes in rows:
            row_dict = bin_row_to_ledger_columns(row_boxes, page_width)
            # Skip completely empty rows
            if any(v.strip() for v in row_dict.values()):
                structured.append(row_dict)

    elif doc_type == "invoice":
        for row_boxes in rows:
            row_dict = bin_row_to_invoice_columns(row_boxes, page_width)
            if any(v.strip() for v in row_dict.values()):
                structured.append(row_dict)

    else:
        # For disclaimer and unknown types: return flat text rows
        for row_boxes in rows:
            text = " ".join(b["text"] for b in row_boxes).strip()
            if text:
                structured.append({"text": text, "boxes": row_boxes})

    logging.info(f"[table_builder] Built {len(structured)} non-empty rows")
    return structured


def find_rows_containing(table: list, keyword: str,
                          column: str = None) -> list:
    """
    Search structured table rows for a keyword.

    Args:
        table:   Output of build_table()
        keyword: Text to search for (case-insensitive)
        column:  If given, only search that column; else search all columns

    Returns:
        list[dict]: Matching rows
    """
    keyword_upper = keyword.upper()
    results = []
    for row in table:
        if column:
            if keyword_upper in str(row.get(column, "")).upper():
                results.append(row)
        else:
            if any(keyword_upper in str(v).upper() for v in row.values()):
                results.append(row)
    return results
