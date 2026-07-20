"""
table/row_cluster.py
=====================
Groups EasyOCR bounding boxes into logical table rows
by proximity of their Y-center coordinates.

Algorithm:
  1. Sort all boxes by y_center (top-to-bottom)
  2. Walk through sorted boxes; if the next box's y_center is
     within `tolerance` pixels of the current row's average y_center,
     add it to the current row, else start a new row.
  3. Within each row, sort boxes left-to-right by x_center.

This handles rows where text boxes are not perfectly aligned
(common in scanned tilted documents).
"""
import logging


def cluster_rows(boxes: list, y_tolerance: int = 8) -> list:
    """
    Group OCR bounding boxes into rows by Y-coordinate proximity.

    Args:
        boxes:       list of box dicts from easyocr_reader.run_easyocr()
        y_tolerance: max pixel distance between y_centers to be in same row.
                     Default 8px works well for 200 DPI scans.
                     Increase to 12-15 for lower resolution scans.

    Returns:
        list[list[dict]]: Each inner list is a row, sorted left-to-right.
                          Rows are ordered top-to-bottom.
    """
    if not boxes:
        return []

    # Sort all boxes top-to-bottom
    sorted_boxes = sorted(boxes, key=lambda b: b["y_center"])

    rows = []
    current_row = [sorted_boxes[0]]
    current_y = sorted_boxes[0]["y_center"]

    for box in sorted_boxes[1:]:
        if abs(box["y_center"] - current_y) <= y_tolerance:
            # Same row — update running average y_center
            current_row.append(box)
            current_y = sum(b["y_center"] for b in current_row) / len(current_row)
        else:
            # New row
            rows.append(sorted(current_row, key=lambda b: b["x_center"]))
            current_row = [box]
            current_y = box["y_center"]

    # Don't forget the last row
    if current_row:
        rows.append(sorted(current_row, key=lambda b: b["x_center"]))

    logging.debug(f"[row_cluster] Grouped {len(boxes)} boxes into {len(rows)} rows (y_tol={y_tolerance}px)")
    return rows


def rows_to_text_lines(rows: list) -> list:
    """
    Convert clustered rows into a list of plain text strings.
    Each row's boxes are joined with spaces, left-to-right.

    Args:
        rows: Output of cluster_rows()

    Returns:
        list[str]: One string per row
    """
    return [" ".join(box["text"] for box in row) for row in rows]
