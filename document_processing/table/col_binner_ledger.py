"""
table/col_binner_ledger.py
===========================
X-coordinate column bins for Mahindra Welcome Bonus Ledger/Account Statement.

Ledger has 6 columns (calibrated from typical A4 scans at 200 DPI):
  Date | Particulars | Vch Type | Vch No | Debit | Credit

X-ranges below are as fraction of page width (0.0 to 1.0) so they
work regardless of exact pixel resolution.
Tune LEDGER_COLUMNS if your scans are significantly different in layout.
"""

# Column definitions: (column_name, x_start_fraction, x_end_fraction)
# Calibrated for standard Tally ledger printouts (A4, portrait)
LEDGER_COLUMNS = [
    ("Date",         0.00, 0.10),
    ("Particulars",  0.10, 0.42),
    ("Vch Type",     0.42, 0.56),
    ("Vch No",       0.56, 0.68),
    ("Debit",        0.68, 0.84),
    ("Credit",       0.84, 1.00),
]


def assign_column_ledger(box: dict, page_width: int) -> str:
    """
    Assign a single OCR box to its ledger column by X-center position.

    Args:
        box:        Box dict from easyocr_reader (must have x_center)
        page_width: Width of the page image in pixels

    Returns:
        str: Column name, or "Unknown" if no range matches
    """
    frac = box["x_center"] / page_width
    for col_name, x_start, x_end in LEDGER_COLUMNS:
        if x_start <= frac < x_end:
            return col_name
    return "Unknown"


def bin_row_to_ledger_columns(row_boxes: list, page_width: int) -> dict:
    """
    Convert a single clustered row into a column-keyed dict.
    If multiple boxes fall in the same column, their texts are joined with space.

    Args:
        row_boxes:  list of box dicts (one row from row_cluster.cluster_rows)
        page_width: page image width in pixels

    Returns:
        dict: { "Date": "01-Jul-25", "Particulars": "WELCOME BONUS...", ... }
    """
    result = {col[0]: [] for col in LEDGER_COLUMNS}
    result["Unknown"] = []

    for box in row_boxes:
        col = assign_column_ledger(box, page_width)
        result[col].append(box["text"])

    # Join multi-text columns
    return {k: " ".join(v).strip() for k, v in result.items()}
