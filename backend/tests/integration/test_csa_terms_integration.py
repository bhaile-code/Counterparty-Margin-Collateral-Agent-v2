"""
Integration test for CSATerms mapping with normalized collateral.

This test validates the complete workflow:
Upload → Parse → Extract → Normalize → Map to CSATerms

Tests with real Credit Suisse / Fifth Third Auto Trust 2008-1 CSA data.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.ade_mapper import ade_mapper
from app.services.collateral_normalizer import CollateralNormalizerService
from app.utils.file_storage import FileStorage
from app.config import settings


def main():
    print("\n" + "="*70)
    print("CSA TERMS INTEGRATION TEST")
    print("="*70 + "\n")

    document_id = "4494b130-c604-48e0-9eb3-2d888504fb43"
    extraction_id = "extract_parse_4494b130-c604-48e0-9eb3-2d888504fb43_20251105_230039_20251105_230112"

    # Step 1: Load extraction
    print("[STEP 1] Loading extraction...")
    extraction_path = Path(settings.extractions_dir) / f"{extraction_id}.json"

    if not extraction_path.exists():
        print(f"[ERROR] Extraction not found: {extraction_path}")
        return False

    with open(extraction_path, 'r', encoding='utf-8') as f:
        extraction_data = json.load(f)

    print(f"[OK] Loaded extraction for: {extraction_data.get('document_id')}\n")

    # Step 2: Check if normalized collateral exists, if not create it
    print("[STEP 2] Loading or creating normalized collateral...")
    normalized_table = FileStorage.load_normalized_collateral(
        document_id,
        settings.normalized_collateral_dir
    )

    if not normalized_table:
        print("[INFO] Normalized collateral not found, creating it...")
        service = CollateralNormalizerService()
        normalized_table = service.normalize_collateral_table(
            ade_extraction=extraction_data,
            document_id=document_id,
            extraction_id=extraction_id
        )
        FileStorage.save_normalized_collateral(
            normalized_table,
            settings.normalized_collateral_dir
        )
        print(f"[OK] Created normalized collateral with {len(normalized_table.collateral_items)} items\n")
    else:
        print(f"[OK] Loaded normalized collateral with {len(normalized_table.collateral_items)} items\n")

    # Step 3: Map to CSATerms
    print("[STEP 3] Mapping to CSATerms...")
    try:
        csa_terms = ade_mapper.map_to_csa_terms(
            ade_extraction=extraction_data,
            document_id=document_id,
            normalized_collateral_table=normalized_table
        )
        print("[OK] Successfully mapped to CSATerms\n")
    except Exception as e:
        print(f"[ERROR] Mapping failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    # Step 4: Display CSATerms summary
    print("="*70)
    print("CSA TERMS SUMMARY")
    print("="*70 + "\n")

    print(f"Counterparty: {csa_terms.counterparty_name}")
    print(f"Threshold: ${csa_terms.threshold:,.2f}")
    print(f"Minimum Transfer Amount: ${csa_terms.minimum_transfer_amount:,.2f}")
    print(f"Rounding: ${csa_terms.rounding:,.2f}")
    print(f"Independent Amount: ${csa_terms.independent_amount:,.2f}")
    print(f"Currency: {csa_terms.currency.value}")
    print(f"Valuation Agent: {csa_terms.valuation_agent}")
    print(f"Effective Date: {csa_terms.effective_date}")
    print(f"\nNormalized Collateral ID: {csa_terms.normalized_collateral_id}")
    print(f"Eligible Collateral Items: {len(csa_terms.eligible_collateral)}")

    # Show collateral types
    collateral_types = {}
    for item in csa_terms.eligible_collateral:
        type_name = item.standardized_type.value
        collateral_types[type_name] = collateral_types.get(type_name, 0) + 1

    print("\nCollateral Types:")
    for type_name, count in sorted(collateral_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {type_name}: {count}")

    # Show sample collateral with maturity buckets
    print("\nSample Collateral with Maturity Buckets:")
    for i, item in enumerate(csa_terms.eligible_collateral[:3], 1):
        print(f"\n  Item {i}: {item.standardized_type.value}")
        print(f"    Rating Event: {item.rating_event}")
        if item.maturity_buckets:
            print(f"    Maturity Buckets: {len(item.maturity_buckets)}")
            for bucket in item.maturity_buckets[:2]:  # Show first 2
                print(f"      - {bucket.min_years}-{bucket.max_years}yr: haircut={bucket.haircut:.2%}")
        else:
            print(f"    Flat Haircut: {item.flat_haircut:.2%}")

    # Step 5: Save CSATerms
    print("\n" + "="*70)
    print("SAVING CSA TERMS")
    print("="*70 + "\n")

    try:
        file_path = FileStorage.save_csa_terms(
            csa_terms,
            settings.csa_terms_dir
        )
        print(f"[OK] Saved CSATerms to: {file_path}\n")
    except Exception as e:
        print(f"[ERROR] Failed to save: {str(e)}\n")
        return False

    # Step 6: Test loading CSATerms
    print("[STEP 4] Testing load from disk...")
    try:
        loaded_csa_terms = FileStorage.load_csa_terms(
            document_id,
            settings.csa_terms_dir
        )
        print(f"[OK] Successfully loaded CSATerms for {loaded_csa_terms.counterparty_name}\n")

        # Verify loaded data matches
        assert loaded_csa_terms.counterparty_name == csa_terms.counterparty_name
        assert loaded_csa_terms.threshold == csa_terms.threshold
        assert len(loaded_csa_terms.eligible_collateral) == len(csa_terms.eligible_collateral)
        print("[OK] Loaded data matches saved data\n")

    except Exception as e:
        print(f"[ERROR] Failed to load: {str(e)}\n")
        return False

    # Step 7: Test helper methods
    print("="*70)
    print("TESTING HELPER METHODS")
    print("="*70 + "\n")

    # Test getting collateral by type
    from app.models.normalized_collateral import StandardizedCollateralType

    rating_event = "Moody's First Trigger Event"
    cash_collateral = csa_terms.get_collateral_by_type(
        StandardizedCollateralType.CASH_USD,
        rating_event
    )

    if cash_collateral:
        print(f"[OK] Found CASH_USD collateral for {rating_event}")
        print(f"     Flat haircut: {cash_collateral.flat_haircut:.2%}")

    treasury_collateral = csa_terms.get_collateral_by_type(
        StandardizedCollateralType.US_TREASURY,
        rating_event
    )

    if treasury_collateral and treasury_collateral.maturity_buckets:
        print(f"[OK] Found US_TREASURY collateral for {rating_event}")
        print(f"     Maturity buckets: {len(treasury_collateral.maturity_buckets)}")

        # Test haircut lookup by maturity
        haircut_2yr = csa_terms.get_haircut_for_maturity(
            StandardizedCollateralType.US_TREASURY,
            rating_event,
            2.5  # 2.5 years maturity
        )
        if haircut_2yr is not None:
            print(f"     Haircut for 2.5yr maturity: {haircut_2yr:.2%}")

    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70 + "\n")

    print("[SUCCESS] All integration tests passed!")
    print("\nComplete Workflow Validated:")
    print("  1. Load extraction")
    print("  2. Create/load normalized collateral")
    print("  3. Map to CSATerms (REQUIRED normalization)")
    print("  4. Save CSATerms")
    print("  5. Load CSATerms from disk")
    print("  6. Test helper methods")
    print("\n")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
