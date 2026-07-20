"""
document_processing/rule_engine.py
====================================
Lightweight declarative rule engine for document validation.

Instead of scattered if/else chains, define each validation as a
ValidationRule object and run them all through RuleEngine.run().

This makes validation logic:
  - Auditable: every check has a name and reason
  - Configurable: enable/disable rules without touching logic
  - Testable: each rule is an isolated unit
  - Consistent: all rules return the same 3-tier status (PASS/FAIL/UNKNOWN)

Usage:
    from document_processing.rule_engine import RuleEngine, ValidationRule
    from document_processing.validation_result import ValidationStatus

    rules = [
        ValidationRule(
            name="chassis_number_match",
            description="Chassis number in document must match dashboard",
            check=lambda ctx: ctx.get("doc_chassis") == ctx.get("portal_chassis"),
            fail_message="Chassis number mismatch",
            severity="ERROR",
        ),
        ValidationRule(
            name="dealer_stamp_present",
            description="Dealer stamp must be present",
            check=lambda ctx: ctx.get("stamp_confidence", 0) >= 0.35,
            unknown_check=lambda ctx: 0.20 <= ctx.get("stamp_confidence", 0) < 0.35,
            fail_message="Dealer stamp is missing",
            unknown_message="Stamp detected but confidence is low — manual review",
            severity="ERROR",
        ),
    ]

    engine = RuleEngine(rules)
    results = engine.run(context)
    issues = issues_from_rule_results(results)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from .validation_result import (
    ValidationStatus, RuleResult, issues_from_rule_results, summary_status
)


@dataclass
class ValidationRule:
    """
    A single named validation rule.

    Attributes:
        name:          Unique identifier used in reports (e.g. "chassis_match")
        description:   Human-readable description of what this rule checks
        check:         Callable(context: dict) -> bool. True = PASS, False = FAIL
        fail_message:  Message returned when check() returns False
        severity:      "ERROR" (blocks approval) or "WARN" (advisory)
        enabled:       Set to False to skip this rule at runtime
        unknown_check: Optional Callable(context) -> bool. If True, status = UNKNOWN
                       instead of FAIL. Use for low-confidence ambiguous cases.
        unknown_message: Message returned when unknown_check() is True
    """
    name:            str
    description:     str
    check:           Callable[[dict], bool]
    fail_message:    str
    severity:        str = "ERROR"    # "ERROR" | "WARN"
    enabled:         bool = True
    unknown_check:   Optional[Callable[[dict], bool]] = None
    unknown_message: str = ""

    def evaluate(self, context: dict) -> RuleResult:
        """
        Run this rule against the context dict.

        Args:
            context: Flat dict of extracted document fields and portal values.
                     Convention: portal values prefixed with "portal_", 
                     document values without prefix.

        Returns:
            RuleResult with PASS/FAIL/UNKNOWN status
        """
        if not self.enabled:
            return RuleResult(
                rule_name=self.name,
                status=ValidationStatus.PASS,
                message=f"[SKIPPED] {self.description}",
                severity=self.severity,
            )

        try:
            passed = bool(self.check(context))
        except Exception as exc:
            logging.warning(f"[rule_engine] Rule '{self.name}' raised exception: {exc}")
            return RuleResult(
                rule_name=self.name,
                status=ValidationStatus.UNKNOWN,
                message=f"Rule evaluation error: {exc}",
                severity=self.severity,
            )

        if passed:
            return RuleResult(
                rule_name=self.name,
                status=ValidationStatus.PASS,
                message=self.description,
                severity=self.severity,
            )

        # Check for UNKNOWN condition before issuing a hard FAIL
        if self.unknown_check is not None:
            try:
                is_unknown = bool(self.unknown_check(context))
            except Exception:
                is_unknown = False

            if is_unknown:
                msg = self.unknown_message or f"{self.description} — ambiguous result, manual review needed"
                logging.info(f"[rule_engine] UNKNOWN '{self.name}': {msg}")
                return RuleResult(
                    rule_name=self.name,
                    status=ValidationStatus.UNKNOWN,
                    message=msg,
                    severity=self.severity,
                )

        logging.info(f"[rule_engine] FAIL '{self.name}': {self.fail_message}")
        return RuleResult(
            rule_name=self.name,
            status=ValidationStatus.FAIL,
            message=self.fail_message,
            severity=self.severity,
        )


class RuleEngine:
    """
    Runs a list of ValidationRules against a context dict.

    Args:
        rules: List of ValidationRule objects to run in order.
    """

    def __init__(self, rules: list[ValidationRule]):
        self.rules = rules

    def run(self, context: dict) -> list[RuleResult]:
        """
        Evaluate all rules against the context.

        Args:
            context: Dict of extracted fields + portal values.
                     Keys follow the convention:
                       portal_*   = values from the dashboard
                       doc_*      = values extracted from the document
                       conf_*     = confidence scores (0.0-1.0)
                       quality_*  = image quality metrics

        Returns:
            list[RuleResult]: One result per enabled rule.
        """
        results = []
        for rule in self.rules:
            result = rule.evaluate(context)
            results.append(result)
            logging.debug(
                f"[rule_engine] {rule.name}: {result.status.value} — {result.message}"
            )
        return results

    def run_and_get_issues(self, context: dict) -> tuple[list[RuleResult], list[str]]:
        """
        Run all rules and return both results and the legacy issue-string list.

        Returns:
            (results, issues): results = full RuleResult list,
                               issues  = list of blocking issue strings
        """
        results = self.run(context)
        issues  = issues_from_rule_results(results)
        return results, issues

    def run_and_summarize(self, context: dict) -> tuple[ValidationStatus, list[str]]:
        """
        Run all rules and return overall status + issues.

        Returns:
            (status, issues): status = PASS/FAIL/UNKNOWN,
                              issues = list of blocking error strings
        """
        results = self.run(context)
        status  = summary_status(results)
        issues  = issues_from_rule_results(results)
        return status, issues


# ── Shared rule factories ──────────────────────────────────────────────────────
# Pre-built common rules that can be reused across doc types

def make_fuzzy_name_rule(
    name: str,
    description: str,
    doc_field: str,
    portal_field: str,
    threshold: float = 80.0,
    unknown_threshold: float = 60.0,
    severity: str = "ERROR",
) -> ValidationRule:
    """
    Create a rule that fuzzy-matches a name field from the document
    against a portal value, using RapidFuzz token_sort_ratio.

    Args:
        name:              Rule identifier
        description:       Human-readable description
        doc_field:         Key in context for the extracted doc value
        portal_field:      Key in context for the portal expected value
        threshold:         Minimum score to PASS (default 80.0)
        unknown_threshold: Score below threshold but above this = UNKNOWN (default 60.0)
        severity:          "ERROR" | "WARN"
    """
    def _check(ctx: dict) -> bool:
        doc_val    = str(ctx.get(doc_field, "") or "").strip().upper()
        portal_val = str(ctx.get(portal_field, "") or "").strip().upper()
        if not doc_val or not portal_val:
            return False
        try:
            from rapidfuzz import fuzz
            score = fuzz.token_sort_ratio(doc_val, portal_val)
            return score >= threshold
        except ImportError:
            return doc_val == portal_val

    def _unknown(ctx: dict) -> bool:
        doc_val    = str(ctx.get(doc_field, "") or "").strip().upper()
        portal_val = str(ctx.get(portal_field, "") or "").strip().upper()
        if not doc_val or not portal_val:
            return True   # Missing = ambiguous
        try:
            from rapidfuzz import fuzz
            score = fuzz.token_sort_ratio(doc_val, portal_val)
            return unknown_threshold <= score < threshold
        except ImportError:
            return False

    return ValidationRule(
        name=name,
        description=description,
        check=_check,
        fail_message=f"{description} — below minimum threshold {threshold}%",
        severity=severity,
        unknown_check=_unknown,
        unknown_message=f"{description} — partial match, manual review needed",
    )


def make_amount_rule(
    name: str,
    description: str,
    doc_amount_field: str,
    portal_amount_field: str,
    tolerance_pct: float = 5.0,
    severity: str = "ERROR",
) -> ValidationRule:
    """
    Create a rule that checks whether a numeric amount in the document
    matches a portal amount within a percentage tolerance.

    Args:
        name:                Rule identifier
        description:         Human-readable description
        doc_amount_field:    Context key for extracted amount (str or float)
        portal_amount_field: Context key for portal expected amount
        tolerance_pct:       Allowed % difference (default 5%)
        severity:            "ERROR" | "WARN"
    """
    def _parse(val) -> Optional[float]:
        try:
            return float(str(val).replace(",", "").strip())
        except (ValueError, TypeError):
            return None

    def _check(ctx: dict) -> bool:
        doc_amt    = _parse(ctx.get(doc_amount_field))
        portal_amt = _parse(ctx.get(portal_amount_field))
        if doc_amt is None or portal_amt is None or portal_amt == 0:
            return False
        pct_diff = abs(doc_amt - portal_amt) / portal_amt * 100
        return pct_diff <= tolerance_pct

    def _unknown(ctx: dict) -> bool:
        doc_amt = _parse(ctx.get(doc_amount_field))
        return doc_amt is None   # Missing amount = UNKNOWN not FAIL

    return ValidationRule(
        name=name,
        description=description,
        check=_check,
        fail_message=f"{description} — amount mismatch exceeds {tolerance_pct}% tolerance",
        severity=severity,
        unknown_check=_unknown,
        unknown_message=f"{description} — amount not found in document",
    )


def make_presence_rule(
    name: str,
    description: str,
    context_field: str,
    present_values: tuple = ("Present", "present", "TRUE", "True", True),
    confidence_field: Optional[str] = None,
    confidence_threshold: float = 0.35,
    unknown_confidence_threshold: float = 0.20,
    severity: str = "ERROR",
) -> ValidationRule:
    """
    Create a rule that checks if something is present (stamp, signature, etc.).
    Supports confidence-based UNKNOWN routing.
    """
    def _check(ctx: dict) -> bool:
        val = ctx.get(context_field)
        if confidence_field and confidence_field in ctx:
            conf = float(ctx.get(confidence_field, 0))
            return conf >= confidence_threshold
        return val in present_values or str(val).lower() in ("present", "true", "yes", "1")

    def _unknown(ctx: dict) -> bool:
        if confidence_field and confidence_field in ctx:
            conf = float(ctx.get(confidence_field, 0))
            return unknown_confidence_threshold <= conf < confidence_threshold
        return False

    return ValidationRule(
        name=name,
        description=description,
        check=_check,
        fail_message=f"{description} — not found",
        severity=severity,
        unknown_check=_unknown,
        unknown_message=f"{description} — detected but confidence too low, manual review needed",
    )
