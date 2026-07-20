"""
document_processing/validation_result.py
==========================================
Defines the 3-tier validation outcome system: PASS / FAIL / UNKNOWN.

Replace simple True/False returns with ValidationStatus across all validators.

UNKNOWN means:
    - Low OCR confidence (< 0.60)
    - Low image quality score (< 40)
    - Ambiguous / partially-matching evidence
    - Anything that needs human review rather than automated rejection

Usage:
    from document_processing.validation_result import (
        ValidationStatus, FieldResult, RuleResult, build_pass, build_fail, build_unknown
    )

    result = build_pass("Chassis number matches dashboard", value="MA1PC2BHXS6F00123")
    result = build_fail("Customer name mismatch", value="JOHN DOE", expected="JANE DOE")
    result = build_unknown("OCR confidence too low for stamp text", confidence=0.42)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ValidationStatus(str, Enum):
    """3-tier validation outcome."""
    PASS    = "PASS"
    FAIL    = "FAIL"
    UNKNOWN = "UNKNOWN"   # Low confidence — requires manual review


@dataclass
class FieldResult:
    """
    A single extracted field with its validation outcome.

    Attributes:
        status:     PASS / FAIL / UNKNOWN
        value:      The actual text extracted from the document
        confidence: OCR or match confidence (0.0-1.0); 1.0 for regex extractions
        expected:   The expected value from the portal/dashboard (optional)
        reason:     Human-readable explanation of the outcome
        source:     Where the value came from: "regex", "ocr", "vision", "portal"
    """
    status:     ValidationStatus
    value:      str
    confidence: float = 1.0
    expected:   str   = ""
    reason:     str   = ""
    source:     str   = "regex"

    @property
    def is_pass(self) -> bool:
        return self.status == ValidationStatus.PASS

    @property
    def is_fail(self) -> bool:
        return self.status == ValidationStatus.FAIL

    @property
    def is_unknown(self) -> bool:
        return self.status == ValidationStatus.UNKNOWN

    def to_dict(self) -> dict:
        return {
            "status":     self.status.value,
            "value":      self.value,
            "confidence": round(self.confidence, 3),
            "expected":   self.expected,
            "reason":     self.reason,
            "source":     self.source,
        }


@dataclass
class RuleResult:
    """
    Result of a single validation rule execution.

    Attributes:
        rule_name: Identifier of the rule (e.g. "chassis_number_match")
        status:    PASS / FAIL / UNKNOWN
        message:   Human-readable description of what passed or failed
        severity:  "ERROR" = blocks approval | "WARN" = advisory only
        field_results: Detailed per-field outcomes that led to this result
    """
    rule_name:     str
    status:        ValidationStatus
    message:       str
    severity:      str = "ERROR"   # "ERROR" | "WARN"
    field_results: list = field(default_factory=list)

    @property
    def blocks_approval(self) -> bool:
        """True if this result should block automatic approval."""
        return self.severity == "ERROR" and self.status in (
            ValidationStatus.FAIL, ValidationStatus.UNKNOWN
        )

    def to_dict(self) -> dict:
        return {
            "rule_name":  self.rule_name,
            "status":     self.status.value,
            "message":    self.message,
            "severity":   self.severity,
        }


# ── Convenience factory functions ──────────────────────────────────────────────

def build_pass(reason: str, value: str = "", confidence: float = 1.0,
               expected: str = "", source: str = "regex") -> FieldResult:
    """Create a PASS FieldResult."""
    return FieldResult(
        status=ValidationStatus.PASS,
        value=value,
        confidence=confidence,
        expected=expected,
        reason=reason,
        source=source,
    )


def build_fail(reason: str, value: str = "", confidence: float = 1.0,
               expected: str = "", source: str = "regex") -> FieldResult:
    """Create a FAIL FieldResult."""
    return FieldResult(
        status=ValidationStatus.FAIL,
        value=value,
        confidence=confidence,
        expected=expected,
        reason=reason,
        source=source,
    )


def build_unknown(reason: str, value: str = "", confidence: float = 0.0,
                  expected: str = "", source: str = "ocr") -> FieldResult:
    """Create an UNKNOWN FieldResult (low confidence — needs human review)."""
    return FieldResult(
        status=ValidationStatus.UNKNOWN,
        value=value,
        confidence=confidence,
        expected=expected,
        reason=reason,
        source=source,
    )


def field_result_from_confidence(
    value: str,
    confidence: float,
    expected: str = "",
    low_conf_threshold: float = 0.60,
    pass_reason: str = "",
    fail_reason: str = "",
    source: str = "ocr",
) -> FieldResult:
    """
    Automatically choose PASS/UNKNOWN based on OCR confidence level.

    - confidence >= low_conf_threshold  → PASS
    - confidence < low_conf_threshold   → UNKNOWN (not FAIL!)

    Args:
        value:               Extracted text
        confidence:          OCR confidence (0.0-1.0)
        expected:            Expected value for display
        low_conf_threshold:  Confidence below which result is UNKNOWN (default 0.60)
        pass_reason:         Reason string on pass
        fail_reason:         Reason string on unknown
        source:              "ocr" | "regex" | "vision"

    Returns:
        FieldResult with PASS or UNKNOWN status
    """
    if confidence >= low_conf_threshold:
        return FieldResult(
            status=ValidationStatus.PASS,
            value=value,
            confidence=confidence,
            expected=expected,
            reason=pass_reason or f"Confidence {confidence:.2f} ≥ threshold {low_conf_threshold:.2f}",
            source=source,
        )
    else:
        return FieldResult(
            status=ValidationStatus.UNKNOWN,
            value=value,
            confidence=confidence,
            expected=expected,
            reason=fail_reason or f"Low OCR confidence {confidence:.2f} < {low_conf_threshold:.2f} — manual review needed",
            source=source,
        )


# ── Aggregate helpers ──────────────────────────────────────────────────────────

def issues_from_rule_results(rule_results: list[RuleResult]) -> list[str]:
    """
    Convert a list of RuleResults to the legacy issue-string list format.
    Only includes results that block approval (FAIL or UNKNOWN with ERROR severity).
    """
    issues = []
    for r in rule_results:
        if r.blocks_approval:
            issues.append(f"[{r.rule_name}] {r.message}")
    return issues


def summary_status(rule_results: list[RuleResult]) -> ValidationStatus:
    """
    Roll up a list of RuleResults into a single overall status.
    - Any ERROR FAIL  → FAIL
    - Any ERROR UNKNOWN → UNKNOWN (if no FAILs)
    - All PASS → PASS
    """
    has_fail    = any(r.status == ValidationStatus.FAIL    and r.severity == "ERROR" for r in rule_results)
    has_unknown = any(r.status == ValidationStatus.UNKNOWN and r.severity == "ERROR" for r in rule_results)

    if has_fail:
        return ValidationStatus.FAIL
    if has_unknown:
        return ValidationStatus.UNKNOWN
    return ValidationStatus.PASS
