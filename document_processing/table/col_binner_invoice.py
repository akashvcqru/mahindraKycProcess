"""
table/col_binner_invoice.py
============================
X-coordinate column bins for Mahindra Tax Invoice (GST invoice).

Invoice has a dense multi-column GST tax table:
  Particulars | HSN/SAC | Taxable Value | CGST Rate | CGST Amt | SGST Rate | SGST Amt | Comp Cess

X-ranges are as fraction of page width (0.0 to 1.0).
Tune INVOICE_COLUMNS if layout differs in your batch.
"""

# Column definitions: (column_name, x_start_fraction, x_end_fraction)
# Calibrated for Mahindra GST invoice A4 portrait layout
INVOICE_COLUMNS = [
    ("Particulars",    0.00, 0.30),
    ("HSN_SAC",        0.30, 0.42),
    ("Taxable_Value",  0.42, 0.54),
    ("CGST_Rate",      0.54, 0.61),
    ("CGST_Amt",       0.61, 0.70),
    ("SGST_Rate",      0.70, 0.77),
    ("SGST_Amt",       0.77, 0.87),
    ("Comp_Cess",      0.87, 1.00),
]


def assign_column_invoice(box: dict, page_width: int) -> str:
    """
    Assign a single OCR box to its invoice column by X-center position.

    Args:
        box:        Box dict from easyocr_reader (must have x_center)
        page_width: Width of the page image in pixels

    Returns:
        str: Column name, or "Unknown" if no range matches
    """
    frac = box["x_center"] / page_width
    for col_name, x_start, x_end in INVOICE_COLUMNS:
        if x_start <= frac < x_end:
            return col_name
    return "Unknown"


def bin_row_to_invoice_columns(row_boxes: list, page_width: int) -> dict:
    """
    Convert a single clustered invoice row into a column-keyed dict.

    Args:
        row_boxes:  list of box dicts (one row from row_cluster.cluster_rows)
        page_width: page image width in pixels

    Returns:
        dict: { "Particulars": "...", "Taxable_Value": "6,96,968.00", ... }
    """
    result = {col[0]: [] for col in INVOICE_COLUMNS}
    result["Unknown"] = []

    for box in row_boxes:
        col = assign_column_invoice(box, page_width)
        result[col].append(box["text"])

    return {k: " ".join(v).strip() for k, v in result.items()}
