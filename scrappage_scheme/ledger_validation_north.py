"""
ledger_validation_north.py
==========================
North Zone – zone-specific ledger validation rules for the Scrappage Scheme.

For LOYALTY scheme:
  The ledger must contain at least ONE of the following bonus line entries:
    • "Green Bonus"
    • "Xmrt"
    • "GST 18%"
    • "Loyalty Bonus"
    • "Scrappage Bonus"

For SCRAPPAGE scheme (non-loyalty):
  No extra zone-specific rule beyond the base validation.
"""

import logging

# ── North Zone Keyword Rules ──────────────────────────────────────────────────
NORTH_LOYALTY_REQUIRED = [
    "GREEN BONUS",
    "XMRT",
    "GST 18%",
    "LOYALTY BONUS",
    "SCRAPPAGE BONUS",
]


def validate_north_zone_ledger(extracted: dict, scheme: str) -> list:
    """
    Validate extracted ledger data against North Zone rules.

    Parameters
    ----------
    extracted : dict
        LLM-extracted fields from the ledger document.
        All field ``text`` and ``amount`` sub-keys are scanned for the keywords.
    scheme : str
        Scheme type for this claim — ``"loyalty"`` or ``"scrappage"``.

    Returns
    -------
    list[str]
        List of hold-reason strings.  Empty list means PASS.
    """
    issues = []

    if scheme == "loyalty":
        # Aggregate all extracted text for a broad scan
        all_text = " ".join(
            (
                str(v.get("text", "")).upper()
                + " "
                + str(v.get("amount", "")).upper()
            )
            for v in extracted.values()
            if isinstance(v, dict)
        )

        matched = next(
            (kw for kw in NORTH_LOYALTY_REQUIRED if kw in all_text),
            None,
        )

        if matched:
            logging.info(
                f"[North Zone Ledger] Loyalty check PASS — found '{matched}' in ledger."
            )
        else:
            issues.append(
                f"North Zone Loyalty: Ledger must contain at least one of: "
                f"{', '.join(NORTH_LOYALTY_REQUIRED)}. "
                f"None found in document."
            )
            logging.warning(
                f"[North Zone Ledger] Loyalty check FAIL — "
                f"none of the required North Zone bonus lines found."
            )

    return issues
