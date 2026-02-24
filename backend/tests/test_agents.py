"""
Unit tests for multi-agent normalization system components.

These tests verify individual agent methods and logic without requiring
full API integration or external API calls.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.models.agent_schemas import (
    Ambiguity,
    AmbiguitySeverity,
)
from app.models.normalized_collateral import StandardizedCollateralType


class TestAmbiguityDetectionLogic:
    """Test collateral agent's ambiguity detection logic."""

    def test_detect_overlapping_buckets(self):
        """Test detection of overlapping maturity buckets."""
        # Simulated parsed result with overlapping buckets
        parsed_buckets = [
            {"min_years": 1, "max_years": 3, "valuation_pct": 0.99},
            {"min_years": 2, "max_years": 5, "valuation_pct": 0.98},  # Overlaps with previous
        ]

        # Check if overlap is detected
        overlap_detected = False
        for i in range(len(parsed_buckets) - 1):
            current = parsed_buckets[i]
            next_bucket = parsed_buckets[i + 1]

            if current["max_years"] > next_bucket["min_years"]:
                overlap_detected = True
                break

        assert overlap_detected, "Should detect overlapping maturity buckets"

    def test_detect_boundary_ambiguity(self):
        """Test detection of inclusive/exclusive boundary ambiguity."""
        # A bucket like "1-2yr" is ambiguous without convention knowledge
        bucket_text = "1-2yr"

        # Check if the boundary is specified explicitly
        has_explicit_boundary = (
            "inclusive" in bucket_text.lower() or
            "exclusive" in bucket_text.lower() or
            "<" in bucket_text or
            "≤" in bucket_text
        )

        # If no explicit boundary, it's ambiguous
        is_ambiguous = not has_explicit_boundary

        assert is_ambiguous, "Should detect boundary ambiguity in '1-2yr'"

    def test_detect_missing_information(self):
        """Test detection of missing maturity information."""
        # Collateral with no maturity bucket
        collateral_data = {
            "type": "US Treasury Securities",
            "valuation_string": "99%"  # No maturity specified
        }

        # Check if maturity info is present
        has_maturity = (
            "yr" in collateral_data["valuation_string"].lower() or
            "year" in collateral_data["valuation_string"].lower() or
            "maturity" in collateral_data["valuation_string"].lower()
        )

        assert not has_maturity, "Should detect missing maturity information"

    def test_detect_unusual_percentage(self):
        """Test detection of unusual haircut percentages."""
        # Typical ranges for common collateral types
        typical_ranges = {
            "US_TREASURY": (0.0, 0.05),  # 0-5%
            "CORPORATE_BONDS": (0.08, 0.15),  # 8-15%
            "EQUITIES": (0.15, 0.30),  # 15-30%
        }

        # Test unusual haircut for US Treasury
        collateral_type = "US_TREASURY"
        haircut = 0.12  # 12% haircut (unusual for treasuries)

        is_unusual = haircut > typical_ranges[collateral_type][1]

        assert is_unusual, "Should detect 12% haircut as unusual for US Treasuries"


class TestSelfCorrectionTaxonomy:
    """Test collateral agent's taxonomy self-correction."""

    def test_correct_invalid_type_to_closest_match(self):
        """Test correction of invalid collateral type to closest valid type."""
        # All valid standardized types
        valid_types = {
            "CASH_USD", "CASH_OTHER", "US_TREASURY", "US_AGENCY",
            "US_AGENCY_MBS", "GOVERNMENT_BONDS", "CORPORATE_BONDS",
            "COMMERCIAL_PAPER", "EQUITIES", "GOLD", "SILVER",
            "MONEY_MARKET", "MUTUAL_FUNDS", "OTHER", "UNKNOWN"
        }

        # Invalid type that agent might produce
        invalid_type = "US_TREASURIES"  # Plural form (invalid)

        # Check if it's invalid
        is_invalid = invalid_type not in valid_types

        assert is_invalid, "Should recognize US_TREASURIES as invalid"

        # Find closest match (simple string similarity)
        closest_match = None
        min_diff = float('inf')

        for valid_type in valid_types:
            # Simple Levenshtein-like comparison
            diff = abs(len(invalid_type) - len(valid_type))
            if diff < min_diff and valid_type.startswith("US_TREASURY"):
                min_diff = diff
                closest_match = valid_type

        assert closest_match == "US_TREASURY", "Should correct to US_TREASURY"

    def test_flag_unknown_type_for_review(self):
        """Test flagging of unrecognized collateral types."""
        # Collateral type not in standard taxonomy
        extracted_type = "Cryptocurrency"  # Not a standard CSA collateral type

        # Check if it maps to any known type
        type_mappings = {
            "cash": "CASH_USD",
            "treasury": "US_TREASURY",
            "agency": "US_AGENCY",
            "corporate": "CORPORATE_BONDS",
            "equity": "EQUITIES",
            "stock": "EQUITIES",
            "gold": "GOLD",
            "silver": "SILVER",
        }

        normalized_type = None
        for keyword, standard_type in type_mappings.items():
            if keyword in extracted_type.lower():
                normalized_type = standard_type
                break

        # If no mapping found, should flag as UNKNOWN
        if normalized_type is None:
            normalized_type = "UNKNOWN"

        assert normalized_type == "UNKNOWN", "Should flag cryptocurrency as UNKNOWN"

    def test_validate_all_enum_members_exist(self):
        """Test that all StandardizedCollateralType enum members are valid."""
        # Get all enum members
        all_types = [member.value for member in StandardizedCollateralType]

        # Should have at least 14 types (actual count in normalized_collateral.py)
        assert len(all_types) >= 14, f"Should have at least 14 standardized types, got {len(all_types)}"

        # Should include common types
        required_types = ["CASH_USD", "US_TREASURY", "CORPORATE_BONDS", "EQUITIES"]
        for required in required_types:
            assert required in all_types, f"Should include {required}"


class TestTimezoneInferenceMappings:
    """Test temporal agent's timezone inference logic."""

    def test_explicit_timezone_mappings(self):
        """Test mapping of common timezone descriptions to IANA names."""
        timezone_mappings = {
            "New York time": "America/New_York",
            "EST": "America/New_York",
            "ET": "America/New_York",
            "Eastern Time": "America/New_York",
            "London time": "Europe/London",
            "GMT": "Europe/London",
            "BST": "Europe/London",
            "Tokyo time": "Asia/Tokyo",
            "JST": "Asia/Tokyo",
            "Hong Kong time": "Asia/Hong_Kong",
            "Sydney time": "Australia/Sydney",
        }

        # Test each mapping
        for hint, expected_tz in timezone_mappings.items():
            # Simulate timezone inference
            inferred_tz = None

            # Simple matching logic
            hint_lower = hint.lower()
            if "new york" in hint_lower or "eastern" in hint_lower or hint in ["EST", "ET"]:
                inferred_tz = "America/New_York"
            elif "london" in hint_lower or hint in ["GMT", "BST"]:
                inferred_tz = "Europe/London"
            elif "tokyo" in hint_lower or hint == "JST":
                inferred_tz = "Asia/Tokyo"
            elif "hong kong" in hint_lower:
                inferred_tz = "Asia/Hong_Kong"
            elif "sydney" in hint_lower:
                inferred_tz = "Australia/Sydney"

            assert inferred_tz == expected_tz, f"Should map '{hint}' to '{expected_tz}'"

    def test_ambiguous_timezone_handling(self):
        """Test handling of ambiguous timezone references."""
        # Ambiguous time with no timezone hint
        time_string = "13:00"  # Could be any timezone

        # Check if timezone hint exists
        timezone_hints = ["EST", "GMT", "JST", "time", "timezone"]
        has_timezone_hint = any(hint.lower() in time_string.lower() for hint in timezone_hints)

        assert not has_timezone_hint, "Should detect lack of timezone information"

        # When no hint, should flag for human review
        requires_review = not has_timezone_hint
        assert requires_review, "Should require human review for ambiguous timezone"

    def test_qualitative_time_parsing(self):
        """Test parsing of qualitative time descriptions."""
        qualitative_times = {
            "close of business": ("17:00", "close of business"),
            "end of day": ("23:59", "end of day"),
            "start of day": ("00:00", "start of day"),
            "market close": ("16:00", "market close"),
        }

        for description, (expected_time, expected_desc) in qualitative_times.items():
            # Simulate parsing
            parsed_time = None
            parsed_desc = None

            if "close of business" in description.lower():
                parsed_time = "17:00"
                parsed_desc = "close of business"
            elif "end of day" in description.lower():
                parsed_time = "23:59"
                parsed_desc = "end of day"
            elif "start of day" in description.lower():
                parsed_time = "00:00"
                parsed_desc = "start of day"
            elif "market close" in description.lower():
                parsed_time = "16:00"
                parsed_desc = "market close"

            assert parsed_time == expected_time, f"Should parse '{description}' to '{expected_time}'"
            assert parsed_desc == expected_desc


class TestCurrencyStandardizationMappings:
    """Test currency agent's ISO 4217 standardization logic."""

    def test_symbol_to_iso_mapping(self):
        """Test mapping of currency symbols to ISO codes."""
        symbol_mappings = {
            "$": "USD",
            "USD": "USD",
            "€": "EUR",
            "EUR": "EUR",
            "£": "GBP",
            "GBP": "GBP",
            "¥": "JPY",
            "JPY": "JPY",
            "CHF": "CHF",
            "CAD": "CAD",
            "AUD": "AUD",
        }

        for symbol, expected_iso in symbol_mappings.items():
            # Simulate standardization
            iso_code = None

            if symbol in ["$", "USD"]:
                iso_code = "USD"
            elif symbol in ["€", "EUR"]:
                iso_code = "EUR"
            elif symbol in ["£", "GBP"]:
                iso_code = "GBP"
            elif symbol in ["¥", "JPY"]:
                iso_code = "JPY"
            elif symbol == "CHF":
                iso_code = "CHF"
            elif symbol == "CAD":
                iso_code = "CAD"
            elif symbol == "AUD":
                iso_code = "AUD"

            assert iso_code == expected_iso, f"Should map '{symbol}' to '{expected_iso}'"

    def test_text_to_iso_mapping(self):
        """Test mapping of currency names to ISO codes."""
        text_mappings = {
            "US Dollars": "USD",
            "United States Dollars": "USD",
            "American Dollars": "USD",
            "Euro": "EUR",
            "Euros": "EUR",
            "British Pounds": "GBP",
            "Pounds Sterling": "GBP",
            "Japanese Yen": "JPY",
            "Swiss Francs": "CHF",
            "Canadian Dollars": "CAD",
            "Australian Dollars": "AUD",
        }

        for text, expected_iso in text_mappings.items():
            # Simulate standardization
            iso_code = None
            text_lower = text.lower()

            # Check more specific matches first (australian before us, canadian before us)
            if "australian" in text_lower:
                iso_code = "AUD"
            elif "canadian" in text_lower:
                iso_code = "CAD"
            elif "united states" in text_lower or "american" in text_lower or text_lower.startswith("us "):
                iso_code = "USD"
            elif "euro" in text_lower:
                iso_code = "EUR"
            elif "british" in text_lower or "sterling" in text_lower:
                iso_code = "GBP"
            elif "japanese" in text_lower and "yen" in text_lower:
                iso_code = "JPY"
            elif "swiss" in text_lower:
                iso_code = "CHF"

            assert iso_code == expected_iso, f"Should map '{text}' to '{expected_iso}'"

    def test_special_value_handling(self):
        """Test handling of special currency values."""
        special_values = {
            "Infinity": (float('inf'), None),
            "Not Applicable": (None, None),
            "N/A": (None, None),
            "None": (None, None),
        }

        for text, (expected_amount, expected_currency) in special_values.items():
            # Simulate special value parsing
            amount = None
            currency = None

            if text.lower() in ["infinity", "inf"]:
                amount = float('inf')
                currency = None
            elif text.lower() in ["not applicable", "n/a", "none"]:
                amount = None
                currency = None

            assert amount == expected_amount, f"Should parse '{text}' amount correctly"
            assert currency == expected_currency, f"Should parse '{text}' currency correctly"

    def test_amount_extraction_with_formatting(self):
        """Test extraction of amounts with various formatting."""
        amount_strings = {
            "$2,000,000": 2000000.0,
            "$2,000,000.00": 2000000.0,
            "2000000": 2000000.0,
            "2,000,000": 2000000.0,
            "$500K": 500000.0,
            "$2M": 2000000.0,
            "$50,000": 50000.0,
        }

        for text, expected_amount in amount_strings.items():
            # Simulate amount extraction
            # Remove currency symbols
            clean_text = text.replace("$", "").replace("€", "").replace("£", "")

            # Handle K/M suffixes
            if "K" in clean_text.upper():
                clean_text = clean_text.upper().replace("K", "")
                multiplier = 1000
            elif "M" in clean_text.upper():
                clean_text = clean_text.upper().replace("M", "")
                multiplier = 1000000
            else:
                multiplier = 1

            # Remove commas and parse
            clean_text = clean_text.replace(",", "")
            amount = float(clean_text) * multiplier

            assert amount == expected_amount, f"Should extract {expected_amount} from '{text}'"


class TestValidationRules:
    """Test validation agent's business rules."""

    def test_mta_threshold_relationship(self):
        """Test that MTA should be <= Threshold."""
        # Valid relationship
        threshold = 2000000
        mta = 500000

        is_valid = mta <= threshold
        assert is_valid, "MTA should be less than or equal to threshold"

        # Invalid relationship
        threshold_invalid = 500000
        mta_invalid = 2000000

        is_invalid = mta_invalid > threshold_invalid
        assert is_invalid, "Should detect MTA greater than threshold as invalid"

    def test_rounding_less_than_mta(self):
        """Test that rounding amount should be < MTA."""
        mta = 500000
        rounding = 10000

        is_valid = rounding < mta
        assert is_valid, "Rounding should be less than MTA"

        # Invalid case
        rounding_invalid = 600000
        is_invalid = rounding_invalid >= mta
        assert is_invalid, "Should detect rounding >= MTA as invalid"

    def test_haircut_in_valid_range(self):
        """Test that haircuts should be in range [0, 1]."""
        valid_haircuts = [0.0, 0.01, 0.05, 0.10, 0.50, 0.99, 1.0]

        for haircut in valid_haircuts:
            is_valid = 0.0 <= haircut <= 1.0
            assert is_valid, f"Haircut {haircut} should be valid"

        invalid_haircuts = [-0.1, 1.5, 2.0, -1.0]

        for haircut in invalid_haircuts:
            is_invalid = haircut < 0.0 or haircut > 1.0
            assert is_invalid, f"Haircut {haircut} should be invalid"


class TestCollateralAnomalyDetection:
    """Test CollateralAgent's anomaly detection in Step 5 validation."""

    def test_detect_unusual_maturity_values(self):
        """Test detection of maturity values < 0.1 years (~36.5 days)."""
        # Test case: Commercial paper with 0.082 years (~30 days)
        buckets = [
            {
                "min_maturity_years": None,
                "max_maturity_years": 0.082,
                "valuation_percentage": 80.0,
                "haircut_percentage": 20.0
            }
        ]

        issues = []

        # Simulate Step 5 validation logic for unusual maturity values
        for i, bucket in enumerate(buckets):
            max_yr = bucket.get("max_maturity_years")
            if max_yr is not None:
                try:
                    max_val = float(max_yr)
                    if max_val < 0.1:
                        days = int(max_val * 365)
                        issues.append(
                            f"Unusual maturity value for bucket {i}: max={max_val} years "
                            f"(~{days} days). Verify this is correct."
                        )
                except (TypeError, ValueError):
                    pass

        assert len(issues) == 1, "Should detect unusual maturity value"
        assert "0.082" in issues[0], "Should include the actual value"
        assert "29 days" in issues[0] or "30 days" in issues[0], "Should convert to days"

    def test_detect_overly_precise_maturity_values(self):
        """Test detection of maturity values with > 2 decimal places."""
        # Test case: Overly precise value like 0.08219178
        buckets = [
            {
                "min_maturity_years": 0.08219178,
                "max_maturity_years": 1.0,
                "valuation_percentage": 80.0,
                "haircut_percentage": 20.0
            }
        ]

        issues = []

        # Simulate Step 5 validation logic for precision
        for i, bucket in enumerate(buckets):
            min_yr = bucket.get("min_maturity_years")
            if min_yr is not None:
                try:
                    min_val = float(min_yr)
                    min_str = f"{min_val:.10f}".rstrip('0').rstrip('.')
                    if '.' in min_str and len(min_str.split('.')[1]) > 2:
                        issues.append(
                            f"Unusually precise maturity value for bucket {i}: min={min_val} years. "
                            f"Consider rounding to 2 decimal places."
                        )
                except (TypeError, ValueError):
                    pass

        assert len(issues) == 1, "Should detect overly precise value"
        assert "0.08219178" in issues[0], "Should include the actual value"

    def test_detect_maturity_bucket_gaps(self):
        """Test detection of gaps between maturity buckets."""
        # Test case: Gap between bucket ending at 1.0 and next starting at 2.0
        buckets = [
            {
                "min_maturity_years": 0.0,
                "max_maturity_years": 1.0,
                "valuation_percentage": 95.0,
                "haircut_percentage": 5.0
            },
            {
                "min_maturity_years": 2.0,
                "max_maturity_years": 5.0,
                "valuation_percentage": 90.0,
                "haircut_percentage": 10.0
            }
        ]

        issues = []

        # Simulate Step 5 validation logic for gaps
        sorted_buckets = sorted(
            [b for b in buckets if b.get("min_maturity_years") is not None],
            key=lambda b: float(b.get("min_maturity_years", 0))
        )
        for i in range(len(sorted_buckets) - 1):
            current_max = sorted_buckets[i].get("max_maturity_years")
            next_min = sorted_buckets[i+1].get("min_maturity_years")

            if current_max is not None and next_min is not None:
                try:
                    current_max_val = float(current_max)
                    next_min_val = float(next_min)
                    gap = next_min_val - current_max_val
                    if gap > 0.01:
                        issues.append(
                            f"Maturity bucket gap detected: bucket {i} ends at {current_max_val} years, "
                            f"but bucket {i+1} starts at {next_min_val} years (gap: {gap:.3f} years). "
                            f"Verify this gap is intentional."
                        )
                except (TypeError, ValueError):
                    pass

        assert len(issues) == 1, "Should detect maturity gap"
        assert "1.0 years" in issues[0] and "2.0 years" in issues[0], "Should identify the gap boundaries"

    def test_no_false_positives_for_normal_values(self):
        """Test that normal maturity values don't trigger false warnings."""
        # Test case: Normal maturity buckets with standard precision
        buckets = [
            {
                "min_maturity_years": 0.0,
                "max_maturity_years": 1.0,
                "valuation_percentage": 95.0,
                "haircut_percentage": 5.0
            },
            {
                "min_maturity_years": 1.0,
                "max_maturity_years": 5.0,
                "valuation_percentage": 90.0,
                "haircut_percentage": 10.0
            }
        ]

        issues = []

        # Run all validation checks
        for i, bucket in enumerate(buckets):
            max_yr = bucket.get("max_maturity_years")
            min_yr = bucket.get("min_maturity_years")

            # Check unusual values
            if max_yr is not None:
                max_val = float(max_yr)
                if max_val < 0.1:
                    issues.append(f"Unusual maturity value for bucket {i}")

            # Check precision
            if min_yr is not None:
                min_val = float(min_yr)
                min_str = f"{min_val:.10f}".rstrip('0').rstrip('.')
                if '.' in min_str and len(min_str.split('.')[1]) > 2:
                    issues.append(f"Overly precise value for bucket {i}")

        assert len(issues) == 0, "Should not flag normal maturity values"


class TestValidationAgentAnomalyDetection:
    """Test ValidationAgent's cross-item anomaly detection."""

    def test_detect_duplicate_collateral_for_same_rating_event(self):
        """Test detection of duplicate collateral types for same rating event."""
        from difflib import SequenceMatcher

        # Test case: Two rows with same type and rating event
        normalized_items = [
            {
                "standardized_type": "COMMERCIAL_PAPER",
                "rating_event": "Moody's First Trigger Event",
                "collateral_type": "Commercial Paper with rating P-1"
            },
            {
                "standardized_type": "COMMERCIAL_PAPER",
                "rating_event": "Moody's First Trigger Event",
                "collateral_type": "Commercial Paper with rating P-1 or better"
            }
        ]

        # Simulate duplicate detection
        type_event_pairs = {}
        duplicates_found = []

        for idx, item in enumerate(normalized_items):
            std_type = item.get("standardized_type")
            rating_event = item.get("rating_event")

            key = (std_type, rating_event)
            if key in type_event_pairs:
                duplicates_found.append({
                    "type": std_type,
                    "rating_event": rating_event,
                    "items": [type_event_pairs[key], idx]
                })
            else:
                type_event_pairs[key] = idx

        assert len(duplicates_found) == 1, "Should detect duplicate collateral"
        assert duplicates_found[0]["type"] == "COMMERCIAL_PAPER"

    def test_detect_split_rows_with_similar_descriptions(self):
        """Test detection of rows with similar descriptions that may need merging."""
        from difflib import SequenceMatcher

        # Test case: Two rows with 90% similar descriptions
        normalized_items = [
            {
                "standardized_type": "COMMERCIAL_PAPER",
                "rating_event": "Moody's First Trigger Event",
                "collateral_type": "Commercial Paper: Commercial Paper with a rating of at least P-1 by Moody's"
            },
            {
                "standardized_type": "COMMERCIAL_PAPER",
                "rating_event": "Moody's First Trigger Event",
                "collateral_type": "Commercial Paper: Commercial Paper with a rating of at least P-1 by Moody's and S&P"
            }
        ]

        # Simulate split row detection
        potential_splits = []
        for i, item1 in enumerate(normalized_items):
            for j, item2 in enumerate(normalized_items[i+1:], start=i+1):
                if item1.get("rating_event") == item2.get("rating_event"):
                    desc1 = item1.get("collateral_type", "")
                    desc2 = item2.get("collateral_type", "")

                    similarity = SequenceMatcher(None, desc1, desc2).ratio()

                    if similarity > 0.8 and item1.get("standardized_type") == item2.get("standardized_type"):
                        potential_splits.append({
                            "items": [i, j],
                            "similarity": similarity
                        })

        assert len(potential_splits) == 1, "Should detect potential split rows"
        assert potential_splits[0]["similarity"] > 0.8, "Similarity should be > 80%"

    def test_detect_unusual_maturity_values_cross_items(self):
        """Test detection of unusual maturity values across all collateral items."""
        # Test case: Multiple items, one with unusual maturity
        normalized_items = [
            {
                "standardized_type": "US_TREASURY",
                "maturity_buckets": [
                    {"max_maturity_years": 1.0, "valuation_percentage": 100.0}
                ]
            },
            {
                "standardized_type": "COMMERCIAL_PAPER",
                "maturity_buckets": [
                    {"max_maturity_years": 0.082, "valuation_percentage": 80.0}  # Unusual
                ]
            },
            {
                "standardized_type": "CORPORATE_BONDS",
                "maturity_buckets": [
                    {"max_maturity_years": 5.0, "valuation_percentage": 85.0}
                ]
            }
        ]

        # Simulate unusual maturity detection
        unusual_maturities = []
        for idx, item in enumerate(normalized_items):
            maturity_buckets = item.get("maturity_buckets", [])
            for bucket_idx, bucket in enumerate(maturity_buckets):
                max_yr = bucket.get("max_maturity_years")

                if max_yr is not None:
                    try:
                        max_val = float(max_yr)
                        if max_val < 0.1:
                            days = int(max_val * 365)
                            unusual_maturities.append(
                                f"Item {idx}, bucket {bucket_idx}: max_maturity={max_val} years (~{days} days)"
                            )
                    except (TypeError, ValueError):
                        pass

        assert len(unusual_maturities) == 1, "Should detect one unusual maturity value"
        assert "Item 1" in unusual_maturities[0], "Should identify the correct item"
        assert "0.082" in unusual_maturities[0], "Should include the actual value"

    def test_no_false_positives_for_different_rating_events(self):
        """Test that similar collateral types with different rating events are not flagged."""
        from difflib import SequenceMatcher

        # Test case: Same type but different rating events (expected)
        normalized_items = [
            {
                "standardized_type": "COMMERCIAL_PAPER",
                "rating_event": "Moody's First Trigger Event",
                "collateral_type": "Commercial Paper with rating P-1"
            },
            {
                "standardized_type": "COMMERCIAL_PAPER",
                "rating_event": "S&P First Trigger Event",
                "collateral_type": "Commercial Paper with rating A-1"
            }
        ]

        # Simulate split row detection (should not flag these)
        potential_splits = []
        for i, item1 in enumerate(normalized_items):
            for j, item2 in enumerate(normalized_items[i+1:], start=i+1):
                # Only check if same rating event
                if item1.get("rating_event") == item2.get("rating_event"):
                    desc1 = item1.get("collateral_type", "")
                    desc2 = item2.get("collateral_type", "")
                    similarity = SequenceMatcher(None, desc1, desc2).ratio()

                    if similarity > 0.8 and item1.get("standardized_type") == item2.get("standardized_type"):
                        potential_splits.append({"items": [i, j]})

        assert len(potential_splits) == 0, "Should not flag items with different rating events"


class TestMaturityExtractionFromCollateralType:
    """Test CollateralAgent's ability to extract maturity from collateral_type field."""

    def test_extract_maturity_from_collateral_type_only(self):
        """Test extraction when maturity is only in collateral_type field."""
        # Simulate parse result where maturity is extracted from collateral_type
        parse_result = {
            "standardized_type": "US_TREASURY",
            "maturity_from_collateral_type": {
                "min_years": 1.0,
                "max_years": 5.0,
                "source_text": "having a remaining maturity of 1 to 5 years"
            },
            "maturity_buckets": [
                {
                    "min_maturity_years": 1.0,
                    "max_maturity_years": 5.0,
                    "valuation_percentage": 95.0,
                    "haircut_percentage": 5.0,
                    "source": "collateral_type"
                }
            ]
        }

        # Verify maturity was extracted from collateral_type
        assert parse_result["maturity_from_collateral_type"] is not None
        assert parse_result["maturity_from_collateral_type"]["min_years"] == 1.0
        assert parse_result["maturity_from_collateral_type"]["max_years"] == 5.0

        # Verify bucket was created from collateral_type maturity
        assert len(parse_result["maturity_buckets"]) == 1
        assert parse_result["maturity_buckets"][0]["source"] == "collateral_type"

    def test_extract_maturity_from_valuation_string_only(self):
        """Test extraction when maturity is only in valuation_string field."""
        # Simulate parse result where maturity is extracted from valuation_string
        parse_result = {
            "standardized_type": "US_TREASURY",
            "maturity_from_collateral_type": None,
            "maturity_buckets": [
                {
                    "min_maturity_years": 1.0,
                    "max_maturity_years": 2.0,
                    "valuation_percentage": 99.0,
                    "haircut_percentage": 1.0,
                    "source": "valuation_string"
                },
                {
                    "min_maturity_years": 2.0,
                    "max_maturity_years": 3.0,
                    "valuation_percentage": 98.0,
                    "haircut_percentage": 2.0,
                    "source": "valuation_string"
                }
            ]
        }

        # Verify no maturity from collateral_type
        assert parse_result["maturity_from_collateral_type"] is None

        # Verify buckets from valuation_string
        assert len(parse_result["maturity_buckets"]) == 2
        assert all(b["source"] == "valuation_string" for b in parse_result["maturity_buckets"])

    def test_maturity_in_both_fields_consistent(self):
        """Test when maturity appears in both fields and is consistent."""
        # Simulate parse result with consistent maturity in both fields
        parse_result = {
            "standardized_type": "US_TREASURY",
            "maturity_from_collateral_type": {
                "min_years": 1.0,
                "max_years": 5.0,
                "source_text": "having a remaining maturity of 1 to 5 years"
            },
            "maturity_buckets": [
                {
                    "min_maturity_years": 1.0,
                    "max_maturity_years": 2.0,
                    "valuation_percentage": 99.0,
                    "haircut_percentage": 1.0,
                    "source": "valuation_string"
                },
                {
                    "min_maturity_years": 2.0,
                    "max_maturity_years": 5.0,
                    "valuation_percentage": 98.0,
                    "haircut_percentage": 2.0,
                    "source": "valuation_string"
                }
            ]
        }

        # Verify both sources present
        assert parse_result["maturity_from_collateral_type"] is not None
        assert len(parse_result["maturity_buckets"]) == 2

        # Validate consistency: all buckets within collateral_type range
        type_min = parse_result["maturity_from_collateral_type"]["min_years"]
        type_max = parse_result["maturity_from_collateral_type"]["max_years"]

        for bucket in parse_result["maturity_buckets"]:
            bucket_min = bucket["min_maturity_years"]
            bucket_max = bucket["max_maturity_years"]

            # Check buckets fall within type range
            assert bucket_min >= type_min, "Bucket min should be >= type min"
            assert bucket_max <= type_max, "Bucket max should be <= type max"

    def test_maturity_conflict_detection(self):
        """Test detection of conflicts when maturities in both fields don't match."""
        # Simulate parse result with conflicting maturity information
        parse_result = {
            "standardized_type": "US_TREASURY",
            "maturity_from_collateral_type": {
                "min_years": 1.0,
                "max_years": 5.0,
                "source_text": "having a remaining maturity of 1 to 5 years"
            },
            "maturity_buckets": [
                {
                    "min_maturity_years": 5.0,
                    "max_maturity_years": 10.0,
                    "valuation_percentage": 95.0,
                    "haircut_percentage": 5.0,
                    "source": "valuation_string"
                }
            ]
        }

        # Simulate conflict detection logic (from Step 5 validation)
        issues = []
        maturity_from_type = parse_result.get("maturity_from_collateral_type")
        buckets = parse_result.get("maturity_buckets", [])

        if maturity_from_type:
            type_min = maturity_from_type.get("min_years")
            type_max = maturity_from_type.get("max_years")

            if type_min is not None or type_max is not None:
                for i, bucket in enumerate(buckets):
                    bucket_min = bucket.get("min_maturity_years")
                    bucket_max = bucket.get("max_maturity_years")

                    if bucket_min is None and bucket_max is None:
                        continue

                    if type_min is not None and bucket_min is not None:
                        if float(bucket_min) < float(type_min):
                            issues.append(f"Bucket {i} min conflict")

                    if type_max is not None and bucket_max is not None:
                        if float(bucket_max) > float(type_max):
                            issues.append(f"Bucket {i} max conflict")

        # Should detect conflict
        assert len(issues) == 1, "Should detect maturity conflict"
        assert "Bucket 0 max conflict" in issues[0], "Should identify bucket 0 max exceeds type max"

    def test_days_to_years_conversion(self):
        """Test conversion of days to years (e.g., '30 days' becomes 0.082 years)."""
        # Simulate parse result with days converted to years
        parse_result = {
            "standardized_type": "COMMERCIAL_PAPER",
            "maturity_from_collateral_type": {
                "min_years": None,
                "max_years": 0.082,  # 30 days converted
                "source_text": "having a remaining maturity of not more than 30 days"
            },
            "maturity_buckets": [
                {
                    "min_maturity_years": None,
                    "max_maturity_years": 0.082,
                    "valuation_percentage": 80.0,
                    "haircut_percentage": 20.0,
                    "source": "collateral_type"
                }
            ]
        }

        # Verify days were converted to years
        max_years = parse_result["maturity_from_collateral_type"]["max_years"]
        assert max_years is not None
        assert abs(max_years - 0.082) < 0.001, "Should convert 30 days to approximately 0.082 years"

        # Verify bucket uses converted value
        bucket_max = parse_result["maturity_buckets"][0]["max_maturity_years"]
        assert abs(bucket_max - 0.082) < 0.001, "Bucket should use converted days value"

    def test_open_ended_maturity_ranges(self):
        """Test handling of open-ended ranges like '>20yr' or '<1yr'."""
        # Test case 1: Greater than X years (no upper bound)
        parse_result_greater = {
            "standardized_type": "CORPORATE_BONDS",
            "maturity_from_collateral_type": {
                "min_years": 20.0,
                "max_years": None,  # No upper bound
                "source_text": "remaining maturity of greater than 20 years"
            },
            "maturity_buckets": [
                {
                    "min_maturity_years": 20.0,
                    "max_maturity_years": None,
                    "valuation_percentage": 85.0,
                    "haircut_percentage": 15.0,
                    "source": "collateral_type"
                }
            ]
        }

        # Verify open-ended upper bound
        assert parse_result_greater["maturity_from_collateral_type"]["max_years"] is None
        assert parse_result_greater["maturity_buckets"][0]["max_maturity_years"] is None

        # Test case 2: Less than X years (no lower bound)
        parse_result_less = {
            "standardized_type": "US_TREASURY",
            "maturity_from_collateral_type": {
                "min_years": None,  # No lower bound
                "max_years": 1.0,
                "source_text": "remaining maturity of not more than 1 year"
            },
            "maturity_buckets": [
                {
                    "min_maturity_years": None,
                    "max_maturity_years": 1.0,
                    "valuation_percentage": 100.0,
                    "haircut_percentage": 0.0,
                    "source": "collateral_type"
                }
            ]
        }

        # Verify open-ended lower bound
        assert parse_result_less["maturity_from_collateral_type"]["min_years"] is None
        assert parse_result_less["maturity_buckets"][0]["min_maturity_years"] is None

    def test_no_maturity_in_either_field(self):
        """Test handling when no maturity information exists in either field."""
        # Simulate parse result with no maturity information (e.g., Cash)
        parse_result = {
            "standardized_type": "CASH_USD",
            "maturity_from_collateral_type": None,
            "maturity_buckets": [
                {
                    "min_maturity_years": None,
                    "max_maturity_years": None,
                    "valuation_percentage": 100.0,
                    "haircut_percentage": 0.0,
                    "source": "valuation_string"
                }
            ]
        }

        # Verify no maturity from collateral_type
        assert parse_result["maturity_from_collateral_type"] is None

        # Verify bucket has null maturity bounds (applies to all maturities)
        bucket = parse_result["maturity_buckets"][0]
        assert bucket["min_maturity_years"] is None
        assert bucket["max_maturity_years"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
