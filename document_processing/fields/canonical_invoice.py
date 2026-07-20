"""
fields/canonical_invoice.py
============================
Canonical field label names for the Mahindra Tax Invoice (GST Invoice).
Used by fuzzy_matcher.py to correct OCR label misreads.
"""

INVOICE_FIELDS = [
    "Customer Name",
    "Customer Code",
    "Address",
    "State",
    "Phone No",
    "PAN No",
    "Aadhar No",
    "Cust GSTIN",
    "Invoice No",
    "Invoice Date",
    "Chassis No",
    "Engine No",
    "Color",
    "HSN Code",
    "OEM Discount",
    "Selling Price",
    "Discount",
    "Taxable Value",
    "CGST Rate",
    "CGST Amount",
    "SGST Rate",
    "SGST Amount",
    "Comp Cess",
    "Grand Total",
    "Amount in Words",
    "Customer Signature",
    "Electronic Reference Number",
    "Dealer Stamp",
    "Authorized Signature",
    "Scheme Type",
    "Scheme Description",
    "Round Off",
]
