#!/usr/bin/env python3
"""
Test script to verify GPT-4o-mini vision extraction consistency improvements.
Tests the same document multiple times to ensure deterministic results.
"""

import json
import logging
import os
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Import the vision extraction function
sys.path.insert(0, str(Path(__file__).parent))
from automate_login import extract_details_via_openai


def test_consistency(pdf_path, num_runs=5):
    """
    Test consistency by extracting the same document multiple times.

    Args:
        pdf_path: Path to PDF document to test
        num_runs: Number of times to extract (default 5)

    Returns:
        dict: Test results with consistency metrics
    """
    if not os.path.exists(pdf_path):
        logging.error(f"Test file not found: {pdf_path}")
        return None

    logging.info(
        f"Testing consistency with {num_runs} extractions of: {os.path.basename(pdf_path)}"
    )
    logging.info("=" * 70)

    results = []

    for run in range(1, num_runs + 1):
        logging.info(f"\n--- Run {run}/{num_runs} ---")
        extracted = extract_details_via_openai(pdf_path)

        if not extracted:
            logging.error(f"Run {run} failed - no data extracted")
            results.append(None)
            continue

        # Log key fields for this run
        doc_type = extracted.get("document_type", "UNKNOWN")
        confidence = extracted.get("confidence_score", 0)
        invoice_no = extracted.get("invoice_number", "N/A")
        chassis_no = extracted.get("chassis_number", "N/A")
        customer_name = extracted.get("customer_name", "N/A")

        logging.info(f"  Type: {doc_type}")
        logging.info(f"  Confidence: {confidence}%")
        logging.info(f"  Invoice #: {invoice_no}")
        logging.info(f"  Chassis #: {chassis_no}")
        logging.info(f"  Customer: {customer_name}")

        results.append(extracted)

    # Analyze consistency
    logging.info("\n" + "=" * 70)
    logging.info("CONSISTENCY ANALYSIS")
    logging.info("=" * 70)

    # Remove None results
    valid_results = [r for r in results if r is not None]

    if len(valid_results) == 0:
        logging.error("All extraction attempts failed!")
        return {"success_rate": 0, "consistency_score": 0, "failed": True}

    success_rate = (len(valid_results) / num_runs) * 100
    logging.info(
        f"✓ Success Rate: {success_rate:.1f}% ({len(valid_results)}/{num_runs} successful)"
    )

    # Check consistency of critical fields
    critical_fields = [
        "invoice_number",
        "chassis_number",
        "customer_name",
        "invoice_date",
        "document_type",
    ]

    consistency_scores = {}

    for field in critical_fields:
        values = [str(r.get(field, "")).strip().upper() for r in valid_results]
        unique_values = set(v for v in values if v and v != "NULL" and v != "N/A")

        if len(unique_values) == 0:
            consistency_scores[field] = 0  # Field not found in any run
            logging.warning(f"⚠ {field}: NOT FOUND in any run")
        elif len(unique_values) == 1:
            consistency_scores[field] = 100  # Perfect consistency
            logging.info(f"✓ {field}: CONSISTENT (value: {list(unique_values)[0]})")
        else:
            consistency = (1 - (len(unique_values) - 1) / len(valid_results)) * 100
            consistency_scores[field] = consistency
            logging.warning(
                f"⚠ {field}: INCONSISTENT - found {len(unique_values)} different values:"
            )
            for val in unique_values:
                count = values.count(val)
                logging.warning(f"    '{val}' appeared {count} time(s)")

    # Calculate overall consistency score
    overall_consistency = sum(consistency_scores.values()) / len(consistency_scores)

    # Check confidence score consistency
    confidences = [r.get("confidence_score", 0) for r in valid_results]
    avg_confidence = sum(confidences) / len(confidences)
    min_confidence = min(confidences)
    max_confidence = max(confidences)

    logging.info(f"\nConfidence Scores:")
    logging.info(f"  Average: {avg_confidence:.1f}%")
    logging.info(f"  Min: {min_confidence}%")
    logging.info(f"  Max: {max_confidence}%")
    logging.info(f"  Range: {max_confidence - min_confidence}%")

    # Final verdict
    logging.info("\n" + "=" * 70)
    logging.info("FINAL VERDICT")
    logging.info("=" * 70)

    if overall_consistency >= 98 and success_rate >= 90:
        verdict = "✅ EXCELLENT - Extraction is highly consistent and reliable"
    elif overall_consistency >= 90 and success_rate >= 80:
        verdict = "✓ GOOD - Extraction is mostly consistent with minor variations"
    elif overall_consistency >= 70 and success_rate >= 60:
        verdict = "⚠ FAIR - Extraction has some inconsistencies, may need tuning"
    else:
        verdict = "❌ POOR - Extraction is unreliable, further improvements needed"

    logging.info(f"Overall Consistency: {overall_consistency:.1f}%")
    logging.info(f"Success Rate: {success_rate:.1f}%")
    logging.info(f"Verdict: {verdict}")

    # Save detailed results
    output_file = f"{os.path.splitext(pdf_path)[0]}_consistency_test.json"
    test_results = {
        "test_file": pdf_path,
        "num_runs": num_runs,
        "success_rate": success_rate,
        "overall_consistency": overall_consistency,
        "field_consistency": consistency_scores,
        "avg_confidence": avg_confidence,
        "confidence_range": max_confidence - min_confidence,
        "verdict": verdict,
        "all_extractions": valid_results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(test_results, f, indent=2, ensure_ascii=False)

    logging.info(f"\nDetailed results saved to: {output_file}")

    return test_results


def main():
    """Main test runner."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test GPT-4o-mini vision extraction consistency"
    )
    parser.add_argument("--pdf", required=True, help="Path to PDF file to test")
    parser.add_argument(
        "--runs", type=int, default=5, help="Number of extraction runs (default: 5)"
    )

    args = parser.parse_args()

    # Check if OPENAI_API_KEY is set
    if not os.getenv("OPENAI_API_KEY"):
        logging.error("OPENAI_API_KEY environment variable not set!")
        logging.error("Please set it before running this test:")
        logging.error("  export OPENAI_API_KEY='your-api-key'  # Linux/Mac")
        logging.error("  set OPENAI_API_KEY=your-api-key      # Windows")
        sys.exit(1)

    # Run consistency test
    results = test_consistency(args.pdf, args.runs)

    if results:
        # Exit with success if consistency is good, error if poor
        if results["overall_consistency"] >= 90 and results["success_rate"] >= 80:
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
