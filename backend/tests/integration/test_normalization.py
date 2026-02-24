"""
Test script for collateral normalization with real Credit Suisse CSA data.

This script tests the AI-powered normalization service using the actual
extraction from the Credit Suisse / Fifth Third Auto Trust 2008-1 CSA.
"""

import json
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent))

from app.services.collateral_normalizer import CollateralNormalizerService
from app.utils.file_storage import FileStorage
from app.config import settings


def load_extraction():
    """Load the existing Credit Suisse extraction."""
    extraction_id = "extract_parse_4494b130-c604-48e0-9eb3-2d888504fb43_20251105_230039_20251105_230112"

    extraction_path = Path(settings.extractions_dir) / f"{extraction_id}.json"

    if not extraction_path.exists():
        print(f"[ERROR] Extraction file not found: {extraction_path}")
        return None

    with open(extraction_path, 'r', encoding='utf-8') as f:
        extraction_data = json.load(f)

    print(f"[OK] Loaded extraction: {extraction_id}")
    print(f"     Document ID: {extraction_data.get('document_id')}")
    return extraction_data


def test_normalization():
    """Test the normalization service."""
    print("\n" + "="*70)
    print("TESTING AI-POWERED COLLATERAL NORMALIZATION")
    print("="*70 + "\n")

    # Load extraction
    extraction_data = load_extraction()
    if not extraction_data:
        return False

    # Create service
    print("[INIT] Initializing CollateralNormalizerService...")
    try:
        service = CollateralNormalizerService()
        print("[OK] Service initialized\n")
    except Exception as e:
        print(f"[ERROR] Failed to initialize service: {str(e)}")
        return False

    # Normalize
    print("[RUN] Normalizing collateral table...")
    print(f"      Found {len(extraction_data['extracted_fields']['eligible_collateral_table'])} collateral rows")
    print(f"      Rating events: {extraction_data['extracted_fields']['column_info']['valuation_column_names']}\n")

    try:
        normalized_table = service.normalize_collateral_table(
            ade_extraction=extraction_data,
            document_id=extraction_data['document_id'],
            extraction_id=extraction_data['extraction_id']
        )
        print("[OK] Normalization completed!\n")
    except Exception as e:
        print(f"[ERROR] Normalization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    # Display results
    print("="*70)
    print("NORMALIZATION RESULTS")
    print("="*70 + "\n")

    print(f"Document ID: {normalized_table.document_id}")
    print(f"Total Items: {len(normalized_table.collateral_items)}")
    print(f"Rating Events: {', '.join(normalized_table.rating_events)}")
    print(f"Model Used: {normalized_table.normalization_model}")
    print(f"Normalized At: {normalized_table.normalized_at}")
    print(f"\nMetadata: {json.dumps(normalized_table.normalization_metadata, indent=2)}\n")

    # Show sample items
    print("="*70)
    print("SAMPLE NORMALIZED ITEMS")
    print("="*70 + "\n")

    for i, item in enumerate(normalized_table.collateral_items[:5], 1):
        print(f"Item {i}: {item.standardized_type.value}")
        print(f"  Base Description: {item.base_description[:80]}...")
        print(f"  Rating Event: {item.rating_event}")

        if item.maturity_buckets:
            print(f"  Maturity Buckets: {len(item.maturity_buckets)}")
            for bucket in item.maturity_buckets[:3]:  # Show first 3
                print(f"    - {bucket.min_years}-{bucket.max_years}yr: "
                      f"valuation={bucket.valuation_percentage:.2%}, "
                      f"haircut={bucket.haircut:.2%}")
        else:
            print(f"  Flat Valuation: {item.flat_valuation_percentage:.2%}")
            print(f"  Flat Haircut: {item.flat_haircut:.2%}")

        if item.confidence:
            print(f"  Confidence: {item.confidence:.2%}")
        if item.notes:
            print(f"  Notes: {item.notes}")
        print()

    if len(normalized_table.collateral_items) > 5:
        print(f"... and {len(normalized_table.collateral_items) - 5} more items\n")

    # Save results
    print("="*70)
    print("SAVING NORMALIZED DATA")
    print("="*70 + "\n")

    try:
        file_path = FileStorage.save_normalized_collateral(
            normalized_table,
            settings.normalized_collateral_dir
        )
        print(f"[OK] Saved normalized data to: {file_path}\n")
    except Exception as e:
        print(f"[ERROR] Failed to save: {str(e)}\n")
        return False

    # Test loading it back
    print("[TEST] Testing load from disk...")
    try:
        loaded_table = FileStorage.load_normalized_collateral(
            normalized_table.document_id,
            settings.normalized_collateral_dir
        )
        print(f"[OK] Successfully loaded {len(loaded_table.collateral_items)} items from disk\n")
    except Exception as e:
        print(f"[ERROR] Failed to load: {str(e)}\n")
        return False

    # Summary
    print("="*70)
    print("TEST SUMMARY")
    print("="*70 + "\n")

    # Count by type
    type_counts = {}
    unknown_count = 0
    for item in normalized_table.collateral_items:
        type_name = item.standardized_type.value
        type_counts[type_name] = type_counts.get(type_name, 0) + 1
        if type_name == "UNKNOWN":
            unknown_count += 1

    print("Collateral Types Found:")
    for type_name, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {type_name}: {count}")

    if unknown_count > 0:
        print(f"\n[WARNING] {unknown_count} items marked as UNKNOWN (require user review)")

    # Count with/without maturity buckets
    with_buckets = sum(1 for item in normalized_table.collateral_items if item.maturity_buckets)
    without_buckets = len(normalized_table.collateral_items) - with_buckets
    print(f"\nMaturity Bucket Analysis:")
    print(f"  With buckets: {with_buckets}")
    print(f"  Without buckets: {without_buckets}")

    print("\n[SUCCESS] All tests passed!\n")
    return True


if __name__ == "__main__":
    success = test_normalization()
    sys.exit(0 if success else 1)
