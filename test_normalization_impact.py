"""
Test script to show normalization impact (before vs. after accuracy)
for document e7f5357f-4419-478e-95fe-b65c80304394
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.normalization_impact_analyzer import NormalizationImpactAnalyzer


def main():
    document_id = "e7f5357f-4419-478e-95fe-b65c80304394"

    # Initialize analyzer
    analyzer = NormalizationImpactAnalyzer()

    # Load extraction data
    extraction_file = Path("backend/data/extractions") / f"extract_parse_{document_id}_20251110_204659_20251110_204749.json"

    if not extraction_file.exists():
        print(f"ERROR: Extraction file not found: {extraction_file}")
        return

    with open(extraction_file, 'r', encoding='utf-8') as f:
        extraction_data = json.load(f)

    # Load normalized data (if exists)
    normalized_dir = Path("backend/data/normalized_multiagent")
    normalized_file = None

    if normalized_dir.exists():
        norm_files = list(normalized_dir.glob(f"*{document_id}*.json"))
        if norm_files:
            normalized_file = norm_files[0]

    if not normalized_file or not normalized_file.exists():
        print("ERROR: No normalized data found for this document")
        print("This feature requires both extraction AND normalization to compare")
        return

    with open(normalized_file, 'r', encoding='utf-8') as f:
        normalized_raw = json.load(f)

    # Build normalized data structure
    normalized_data = {
        "normalized_collateral": normalized_raw.get("normalized_collateral_table", []),
        "temporal": normalized_raw.get("temporal_fields", {}),
        "currency": normalized_raw.get("currency_fields", {}),
        "overall_confidence": normalized_raw.get("overall_confidence", 0.0)
    }

    print("=" * 80)
    print(f"NORMALIZATION IMPACT ANALYSIS")
    print(f"Document ID: {document_id}")
    print("=" * 80)
    print()

    # Generate comparison report
    report = analyzer.generate_comparison_report(
        document_id="csa_credit_suisse",  # Using Credit Suisse ground truth
        extraction_data=extraction_data.get("extracted_fields", {}),
        normalized_data=normalized_data
    )

    if not report:
        print("Ground Truth Status: NOT AVAILABLE")
        print("Cannot calculate normalization impact without ground truth")
        return

    # Display results
    overall = report["overall_impact"]
    before = overall["before_normalization"]
    after = overall["after_normalization"]
    improvement = overall["improvement"]

    print("ACCURACY COMPARISON")
    print("-" * 80)
    print(f"Before Normalization (Raw Extraction):  {before['accuracy']:.2%}")
    print(f"After Normalization (Multi-Agent):      {after['accuracy']:.2%}")
    print()
    print(f"Absolute Improvement:    {improvement['absolute']:+.2%}")
    print(f"Percentage Improvement:  {improvement['percentage']:+.2f}%")
    print()
    print(f"Improvement Description: {improvement['description']}")
    print()

    # Quality levels
    summary = report["summary"]
    print("QUALITY ASSESSMENT")
    print("-" * 80)
    print(f"Before Quality: {summary['before_quality']}")
    print(f"After Quality:  {summary['after_quality']}")
    print(f"Normalization Effective: {'Yes' if summary['normalization_effective'] else 'No'}")
    print()

    # Detailed metrics
    print("DETAILED METRICS")
    print("-" * 80)
    print()
    print("BEFORE NORMALIZATION:")
    before_metrics = before['metrics']
    print(f"  Precision:        {before_metrics.get('precision', 0):.2%}")
    print(f"  Recall:           {before_metrics.get('recall', 0):.2%}")
    print(f"  F1 Score:         {before_metrics.get('f1_score', 0):.2%}")
    print(f"  Error Rate:       {before_metrics.get('error_rate', 0):.2%}")
    print()
    print("AFTER NORMALIZATION:")
    after_metrics = after['metrics']
    print(f"  Precision:        {after_metrics.get('precision', 0):.2%}")
    print(f"  Recall:           {after_metrics.get('recall', 0):.2%}")
    print(f"  F1 Score:         {after_metrics.get('f1_score', 0):.2%}")
    print(f"  Error Rate:       {after_metrics.get('error_rate', 0):.2%}")
    print()

    # Field-level impact
    if "field_level_impact" in report and report["field_level_impact"]:
        field_impact = report["field_level_impact"]

        if field_impact.get("field_improvements"):
            print("FIELD-LEVEL IMPROVEMENTS")
            print("-" * 80)

            improvements = field_impact["field_improvements"]
            for field, data in improvements.items():
                improvement_val = data["improvement"]
                arrow = "↑" if improvement_val > 0 else "↓" if improvement_val < 0 else "→"
                print(f"  {arrow} {field:35s}  {data['before']:.2%} → {data['after']:.2%}  ({improvement_val:+.2%})")

            print()

            # Most improved fields
            if field_impact.get("most_improved"):
                print(f"Most Improved: {', '.join(field_impact['most_improved'][:3])}")

            # Degraded fields
            if field_impact.get("degraded_fields"):
                print(f"Degraded: {', '.join(field_impact['degraded_fields'])}")

            print()

    # Processing value
    if "processing_value" in report:
        value = report["processing_value"]
        print("PROCESSING VALUE ASSESSMENT")
        print("-" * 80)
        print(f"Value Rating:       {value['value_rating']}")
        print(f"Justification:      {value['justification']}")
        print(f"Worth Processing:   {'Yes' if value['worth_processing'] else 'No'}")
        print()

    # Recommendations
    if "recommendations" in report and report["recommendations"]:
        print("RECOMMENDATIONS")
        print("-" * 80)

        for rec in report["recommendations"]:
            priority_mark = {
                "critical": "[!!!]",
                "high": "[!! ]",
                "medium": "[!  ]",
                "low": "[   ]"
            }.get(rec.get("priority", "low"), "[   ]")

            print(f"{priority_mark} {rec.get('message')}")
            print(f"       Action: {rec.get('action')}")

            if "affected_fields" in rec:
                print(f"       Fields: {', '.join(rec['affected_fields'])}")

            print()

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
