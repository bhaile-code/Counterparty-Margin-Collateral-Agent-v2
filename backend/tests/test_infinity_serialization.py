"""
Test infinity serialization round-trip.

Ensures that float('inf') values are properly saved to JSON and loaded back.
"""

import json
import os
import tempfile
from math import inf

import pytest
from app.models.schemas import CSATerms, Currency
from app.utils.file_storage import FileStorage, InfinityEncoder


def test_infinity_encoder_direct():
    """Test InfinityEncoder handles infinity values correctly."""
    data = {
        "threshold": float('inf'),
        "negative_threshold": float('-inf'),
        "normal_value": 1000.0
    }

    json_str = json.dumps(data, cls=InfinityEncoder)

    # Check that infinity is serialized as "Infinity" string (with quotes - valid JSON)
    assert '"threshold": "Infinity"' in json_str or '"threshold":"Infinity"' in json_str
    assert '"-Infinity"' in json_str or '"-Infinity"' in json_str  # Negative infinity as quoted string
    assert '"normal_value": 1000' in json_str

    # For round-trip, we need to parse the infinity strings back
    loaded = json.loads(json_str)
    # After json.loads, we get strings - need to convert back to infinity
    loaded = InfinityEncoder.parse_infinity(loaded)
    assert loaded['threshold'] == inf
    assert loaded['negative_threshold'] == float('-inf')
    assert loaded['normal_value'] == 1000.0


def test_csa_terms_infinity_round_trip():
    """Test CSATerms with infinity thresholds serializes and deserializes correctly."""
    # Create CSATerms with infinity threshold
    csa_terms = CSATerms(
        party_a="Test Party A",
        party_b="Test Party B",
        party_a_threshold=float('inf'),
        party_b_threshold=0.0,
        party_a_minimum_transfer_amount=50000.0,
        party_b_minimum_transfer_amount=50000.0,
        party_a_independent_amount=0.0,
        party_b_independent_amount=0.0,
        rounding=10000.0,
        currency=Currency.USD,
        normalized_collateral_id="test-id",
        eligible_collateral=[],
        source_document_id="test-doc"
    )

    # Verify model has infinity
    assert csa_terms.party_a_threshold == inf
    assert csa_terms.party_b_threshold == 0.0

    # Serialize to JSON using Pydantic
    json_data = csa_terms.model_dump(mode="json")

    # Save to temp file using FileStorage
    with tempfile.TemporaryDirectory() as tmpdir:
        saved_path = FileStorage.save_json(json_data, tmpdir, "test_csa_terms.json")

        # Read raw JSON file
        with open(saved_path, 'r') as f:
            raw_json = f.read()

        # Check that JSON contains "Infinity" as a quoted string (valid JSON)
        assert 'Infinity' in raw_json
        assert '"party_a_threshold": "Infinity"' in raw_json or '"party_a_threshold":"Infinity"' in raw_json

        # Load back using FileStorage (should convert "Infinity" string back to float('inf'))
        loaded_data = FileStorage.load_json(tmpdir, "test_csa_terms.json")

        # Check loaded data - should be numeric infinity, not string
        assert loaded_data['party_a_threshold'] == inf
        assert loaded_data['party_b_threshold'] == 0.0

        # Parse with Pydantic
        loaded_csa_terms = CSATerms(**loaded_data)

        # Verify round-trip preservation
        assert loaded_csa_terms.party_a_threshold == inf
        assert loaded_csa_terms.party_b_threshold == 0.0


def test_normalize_threshold_with_infinity_prefix():
    """Test that normalize_threshold handles 'Infinity; provided that...' strings."""
    from app.utils.constants import normalize_threshold

    # Test exact "Infinity"
    assert normalize_threshold("Infinity") == inf
    assert normalize_threshold("infinity") == inf

    # Test "Infinity" with conditions (real-world case)
    complex_str = "Infinity; provided that for (a) so long as the Moody's First Rating Trigger Requirements apply..."
    assert normalize_threshold(complex_str) == inf

    # Test "Not Applicable" -> 0
    assert normalize_threshold("Not Applicable") == 0.0
    assert normalize_threshold("N/A") == 0.0

    # Test numeric strings
    assert normalize_threshold("1000000") == 1000000.0
    assert normalize_threshold(50000.0) == 50000.0


def test_csa_terms_field_validator():
    """Test CSATerms field validator normalizes threshold strings correctly."""
    # Create with "Infinity" string
    csa_terms = CSATerms(
        party_a="Test Party A",
        party_b="Test Party B",
        party_a_threshold="Infinity; provided that for testing",
        party_b_threshold="Not Applicable",
        party_a_minimum_transfer_amount=50000.0,
        party_b_minimum_transfer_amount=50000.0,
        party_a_independent_amount=0.0,
        party_b_independent_amount=0.0,
        rounding=10000.0,
        currency=Currency.USD,
        normalized_collateral_id="test-id",
        eligible_collateral=[],
        source_document_id="test-doc"
    )

    # Field validator should have converted strings to proper values
    assert csa_terms.party_a_threshold == inf
    assert csa_terms.party_b_threshold == 0.0


if __name__ == '__main__':
    pytest.main([__file__, "-v"])
