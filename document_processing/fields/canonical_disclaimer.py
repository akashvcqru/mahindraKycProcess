"""
fields/canonical_disclaimer.py
================================
Canonical field label names for the Mahindra Customer Disclaimer Document.
Used by fuzzy_matcher.py to correct OCR label misreads.
"""

DISCLAIMER_FIELDS = [
    "Customer Name",
    "Customer Signature",
    "Date",
    "Chassis No",
    "Invoice No",
    "Invoice Date",
    "Dealer Name",
    "Dealer Stamp",
    "Authorized Signature",
    "Vehicle Model",
    "Welcome Bonus Amount",
    "OEM Share Amount",
    "Total Amount",
    "Declaration",
    "Disclaimer",
    "I hereby confirm",
    "I agree",
    "Customer Mobile",
    "Customer Address",
]
