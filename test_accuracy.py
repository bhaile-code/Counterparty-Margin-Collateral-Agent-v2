"""
Test script to validate accuracy for document e7f5357f-4419-478e-95fe-b65c80304394
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.accuracy_validator import AccuracyValidator


def main():
    document_id = "e7f5357f-4419-478e-95fe-b65c80304394"

    # Initialize validator
    validator = AccuracyValidator()

    # Load extraction data
    extraction_file = Path("backend/data/extractions") / f"extract_parse_{document_id}_20251110_204659_20251110_204749.json"

    if not extraction_file.exists():
        print(f"ERROR: Extraction file not found: {extraction_file}")
        return

    with open(extraction_file, 'r', encoding='utf-8') as f:
        extraction_data = json.load(f)

    print("=" * 80)
    print(f"ACCURACY VALIDATION REPORT")
    print(f"Document ID: {document_id}")
    print("=" * 80)
    print()

    # Validate extraction accuracy
    print("EXTRACTION ACCURACY")
    print("-" * 80)

    result = validator.validate_extraction(
        document_id="csa_credit_suisse",  # Using ground truth for Credit Suisse CSA
        extracted_fields=extraction_data.get("extracted_fields", {})
    )

    if result.get("error"):
        print(f"Ground Truth Status: NOT AVAILABLE")
        print(f"Message: {result.get('error')}")
        print()
        print("NOTE: To get accuracy metrics, you need to:")
        print("  1. Create ground truth file at:")
        print(f"     backend/tests/ground_truth/expected_extractions/csa_credit_suisse_extraction.json")
        print("  2. Or use the existing Credit Suisse ground truth if this is the same document")
        print()
    else:
        overall = result.get("overall_metrics", {})

        print(f"Overall Accuracy:  {overall.get('accuracy', 0):.2%}")
        print(f"Precision:         {overall.get('precision', 0):.2%}")
        print(f"Recall:            {overall.get('recall', 0):.2%}")
        print(f"F1 Score:          {overall.get('f1_score', 0):.2%}")
        print(f"Error Rate:        {overall.get('error_rate', 0):.2%}")
        print()
        print(f"True Positives:    {overall.get('true_positives', 0)}")
        print(f"False Positives:   {overall.get('false_positives', 0)}")
        print(f"False Negatives:   {overall.get('false_negatives', 0)}")
        print(f"Total Fields:      {overall.get('total_fields', 0)}")
        print()

        # Field-level scores
        print("FIELD-LEVEL ACCURACY")
        print("-" * 80)

        field_scores = result.get("field_scores", {})
        for section, scores in field_scores.items():
            print(f"\n{section.upper()}:")
            if isinstance(scores, dict):
                if "row_matches" in scores:
                    # Collateral table
                    print(f"  Row Count Match: {scores.get('row_count_match', False)}")
                    print(f"  Expected Rows: {scores.get('expected_rows', 0)}")
                    print(f"  Actual Rows: {scores.get('actual_rows', 0)}")
                    print(f"  Average Match Score: {scores.get('average_match_score', 0):.2%}")
                else:
                    # Regular fields
                    for field, score in scores.items():
                        status = "[PASS]" if score >= 0.95 else "[FAIL]" if score < 0.80 else "[WARN]"
                        print(f"  {status} {field:30s} {score:.2%}")

        # Errors
        errors = result.get("errors", [])
        if errors:
            print()
            print("ERRORS DETECTED")
            print("-" * 80)
            print(f"Total Errors: {len(errors)}")
            print()

            # Group by type
            by_type = {}
            for error in errors:
                error_type = error.get("type", "unknown")
                if error_type not in by_type:
                    by_type[error_type] = []
                by_type[error_type].append(error)

            for error_type, error_list in by_type.items():
                print(f"\n{error_type.upper().replace('_', ' ')} ({len(error_list)}):")
                for i, error in enumerate(error_list[:5], 1):  # Show first 5
                    print(f"  {i}. {error.get('section', 'unknown')}.{error.get('field', 'unknown')}")
                    print(f"     Expected: {error.get('expected', 'N/A')}")
                    print(f"     Actual:   {error.get('actual', 'N/A')}")
                    if 'similarity' in error:
                        print(f"     Similarity: {error.get('similarity', 0):.2%}")

                if len(error_list) > 5:
                    print(f"  ... and {len(error_list) - 5} more")

        # Pass/Fail
        print()
        print("VALIDATION RESULT")
        print("-" * 80)
        passed = result.get("passed", False)
        if passed:
            print("STATUS: PASSED")
            print("Document meets accuracy threshold (>=95%)")
        else:
            print("STATUS: FAILED")
            print("Document below accuracy threshold (<95%)")
            print("Recommendation: Flag for human review")

    print()
    print("=" * 80)

    # Show extracted data summary
    print()
    print("EXTRACTED DATA SUMMARY")
    print("-" * 80)

    extracted = extraction_data.get("extracted_fields", {})

    if "agreement_info" in extracted:
        info = extracted["agreement_info"]
        print(f"Agreement Title: {info.get('agreement_title', 'N/A')}")
        print(f"Agreement Date:  {info.get('agreement_date', 'N/A')}")
        print(f"Party A:         {info.get('party_a', 'N/A')}")
        print(f"Party B:         {info.get('party_b', 'N/A')}")

    if "core_margin_terms" in extracted:
        terms = extracted["core_margin_terms"]
        print(f"\nParty A Threshold: {terms.get('party_a_threshold', 'N/A')}")
        print(f"Party B Threshold: {terms.get('party_b_threshold', 'N/A')}")
        print(f"Base Currency:     {terms.get('base_currency', 'N/A')}")

    if "eligible_collateral_table" in extracted:
        collateral = extracted["eligible_collateral_table"]
        print(f"\nCollateral Items: {len(collateral)}")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
