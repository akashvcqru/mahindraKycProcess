"""
ledger_validation_east.py
=========================
East Zone – zone-specific ledger validation rules for the Scrappage Scheme.

For LOYALTY scheme:
  The ledger must contain either "SCRAPPAGE BONUS" or "WELCOME BONUS" strictly.

For SCRAPPAGE scheme (non-loyalty):
  No extra zone-specific rule beyond the base validation.
"""

import logging

# ── East Zone Keyword Rules ──────────────────────────────────────────────────
EAST_LOYALTY_REQUIRED = ["SCRAPPAGE BONUS", "WELCOME BONUS"]


def validate_east_zone_ledger(extracted: dict, scheme: str) -> list:
    """
    Validate extracted ledger data against East Zone rules.

    Parameters
    ----------
    extracted : dict
        LLM-extracted fields from the ledger document.
        Expected key: ``scrappage_bonus`` with sub-keys ``text`` and ``amount``.
    scheme : str
        Scheme type for this claim — ``"loyalty"`` or ``"scrappage"``.

    Returns
    -------
    list[str]
        List of hold-reason strings.  Empty list means PASS.
    """
    issues = []

    if scheme == "loyalty":
        # Gather all text from the extracted bonus field
        bonus_text = extracted.get("scrappage_bonus", {}).get("text", "").upper()

        matched = next(
            (kw for kw in EAST_LOYALTY_REQUIRED if kw in bonus_text),
            None,
        )

        if matched:
            logging.info(
                f"[East Zone Ledger] Loyalty check PASS — found '{matched}' in ledger."
            )
        else:
            issues.append(
                f"East Zone Loyalty: Ledger must strictly contain "
                f"'Scrappage Bonus' or 'Welcome Bonus'. "
                f"Found: '{bonus_text or 'NOTHING'}'"
            )
            logging.warning(
                f"[East Zone Ledger] Loyalty check FAIL — "
                f"neither 'Scrappage Bonus' nor 'Welcome Bonus' found."
            )

    return issues
