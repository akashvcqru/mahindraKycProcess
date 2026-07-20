"""
fields/canonical_ledger.py
===========================
Canonical field label names for the Mahindra Welcome Bonus Ledger.
Used by fuzzy_matcher.py to correct OCR label misreads.
"""

# Headers expected in a Tally ledger account statement
LEDGER_FIELDS = [
    "Date",
    "Particulars",
    "Vch Type",
    "Vch No",
    "Debit",
    "Credit",
    "Opening Balance",
    "Closing Balance",
    "Welcome Bonus",
    "Loyalty Bonus",
    "Dealership Name",
    "Customer Name",
    "Account Name",
    "Ledger Account",
    "Statement of Account",
    "Dr",
    "Cr",
]
