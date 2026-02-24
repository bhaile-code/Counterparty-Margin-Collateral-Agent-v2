"""
Accuracy Benchmark Tests

Automated tests that validate extraction and normalization accuracy
against ground truth datasets.
"""

import pytest
import json
from pathlib import Path
from typing import Dict, Any

from app.services.accuracy_validator import AccuracyValidator, calculate_aggregate_accuracy


class TestExtractionAccuracy:
    """Test extraction accuracy against ground truth."""

    @pytest.fixture
    def validator(self):
        """Create accuracy validator instance."""
        return AccuracyValidator()

    @pytest.fixture
    def sample_extraction(self):
        """Load sample extraction data."""
        # This would load actual extraction data in practice
        return {
            "document_id": "csa_credit_suisse",
            "extracted_fields": {
                "agreement_info": {
                    "agreement_title": "CREDIT SUPPORT ANNEX to the Schedule to the ISDA MASTER AGREEMENT",
                    "agreement_date": "March 31, 2008",
                    "party_a": "CREDIT SUISSE INTERNATIONAL",
                    "party_b": "FIFTH THIRD AUTO TRUST 2008-1",
                    "exhibit_number": "EX-10.7"
                },
                "core_margin_terms": {
                    "party_a_threshold": "Infinity",
                    "party_b_threshold": "Not Applicable",
                    "party_a_min_transfer_amount": "$50,000",
                    "party_b_min_transfer_amount": "$50,000",
                    "rounding": "$10,000",
                    "base_currency": "US Dollars",
                    "party_a_independent_amount": "Not Applicable",
                    "party_b_independent_amount": "Not Applicable"
                },
                "valuation_timing": {
                    "notification_time": "1:00 p.m., New York time",
                    "valuation_time": "close of business on the Local Business Day before the Valuation Date",
                    "valuation_agent": "Party A"
                }
            }
        }

    def test_ground_truth_exists(self, validator):
        """Test that ground truth files exist."""
        gt_extraction = validator.load_ground_truth_extraction("csa_credit_suisse")
        assert gt_extraction is not None, "Ground truth extraction file should exist"
        assert "expected_fields" in gt_extraction, "Ground truth should have expected_fields"

        gt_normalized = validator.load_ground_truth_normalized("csa_credit_suisse")
        assert gt_normalized is not None, "Ground truth normalized file should exist"

    def test_agreement_info_extraction_accuracy(self, validator, sample_extraction):
        """Test extraction accuracy for agreement info fields."""
        result = validator.validate_extraction(
            document_id="csa_credit_suisse",
            extracted_fields=sample_extraction["extracted_fields"]
        )

        assert not result.get("error"), "Validation should not error"

        # Check agreement_info section accuracy
        agreement_scores = result.get("field_scores", {}).get("agreement_info", {})
        assert agreement_scores, "Should have agreement_info scores"

        # All agreement fields should be 100% accurate
        for field, score in agreement_scores.items():
            assert score >= 0.95, f"Agreement field '{field}' accuracy {score} below 95%"

    def test_core_margin_terms_extraction_accuracy(self, validator, sample_extraction):
        """Test extraction accuracy for core margin terms."""
        result = validator.validate_extraction(
            document_id="csa_credit_suisse",
            extracted_fields=sample_extraction["extracted_fields"]
        )

        assert not result.get("error"), "Validation should not error"

        # Check core_margin_terms section accuracy
        margin_scores = result.get("field_scores", {}).get("core_margin_terms", {})
        assert margin_scores, "Should have core_margin_terms scores"

        # Critical fields should be very accurate
        critical_fields = ["party_a_threshold", "party_b_threshold", "base_currency"]
        for field in critical_fields:
            if field in margin_scores:
                assert margin_scores[field] >= 0.95, \
                    f"Critical field '{field}' accuracy {margin_scores[field]} below 95%"

    def test_overall_extraction_accuracy_threshold(self, validator, sample_extraction):
        """Test that overall extraction accuracy meets minimum threshold."""
        result = validator.validate_extraction(
            document_id="csa_credit_suisse",
            extracted_fields=sample_extraction["extracted_fields"]
        )

        assert not result.get("error"), "Validation should not error"

        overall_metrics = result.get("overall_metrics", {})
        accuracy = overall_metrics.get("accuracy", 0.0)

        # Target: 95% overall accuracy for extraction
        assert accuracy >= 0.95, \
            f"Overall extraction accuracy {accuracy} below target 95%"

    def test_extraction_precision_recall(self, validator, sample_extraction):
        """Test precision and recall metrics."""
        result = validator.validate_extraction(
            document_id="csa_credit_suisse",
            extracted_fields=sample_extraction["extracted_fields"]
        )

        overall_metrics = result.get("overall_metrics", {})

        precision = overall_metrics.get("precision", 0.0)
        recall = overall_metrics.get("recall", 0.0)
        f1_score = overall_metrics.get("f1_score", 0.0)

        # Both precision and recall should be high
        assert precision >= 0.90, f"Precision {precision} below 90%"
        assert recall >= 0.90, f"Recall {recall} below 90%"
        assert f1_score >= 0.90, f"F1 score {f1_score} below 90%"

    def test_no_critical_extraction_failures(self, validator, sample_extraction):
        """Test that no critical fields are completely missing."""
        result = validator.validate_extraction(
            document_id="csa_credit_suisse",
            extracted_fields=sample_extraction["extracted_fields"]
        )

        errors = result.get("errors", [])

        # Check for extraction failures (missing fields)
        extraction_failures = [
            e for e in errors
            if e.get("type") == "extraction_failure"
        ]

        # Critical fields should never fail to extract
        critical_fields = [
            "party_a", "party_b", "agreement_date", "base_currency",
            "party_a_threshold", "party_b_threshold"
        ]

        for error in extraction_failures:
            field = error.get("field")
            assert field not in critical_fields, \
                f"Critical field '{field}' failed to extract"


class TestNormalizationAccuracy:
    """Test normalization accuracy against ground truth."""

    @pytest.fixture
    def validator(self):
        """Create accuracy validator instance."""
        return AccuracyValidator()

    @pytest.fixture
    def sample_normalized(self):
        """Load sample normalized data."""
        return {
            "document_id": "csa_credit_suisse",
            "normalized_collateral": [
                {
                    "original_text": "Cash: US Dollars in depository account form: 100%",
                    "standardized_type": "CASH_USD",
                    "maturity_buckets": [
                        {
                            "min_maturity_years": None,
                            "max_maturity_years": None,
                            "valuation_percentage": 100.0,
                            "haircut_percentage": 0.0
                        }
                    ],
                    "confidence": 1.0
                }
            ],
            "temporal": {
                "notification_time": {
                    "time": "13:00:00",
                    "timezone": "America/New_York",
                    "confidence": 0.95
                }
            },
            "currency": {
                "base_currency": {
                    "currency_code": "USD",
                    "confidence": 1.0
                },
                "mta_party_a": {
                    "amount": 50000.0,
                    "currency_code": "USD",
                    "is_infinity": False,
                    "confidence": 0.95
                }
            },
            "overall_confidence": 0.95
        }

    def test_collateral_type_classification_accuracy(self, validator, sample_normalized):
        """Test accuracy of collateral type classification."""
        result = validator.validate_normalization(
            document_id="csa_credit_suisse",
            normalized_data=sample_normalized
        )

        assert not result.get("error"), "Validation should not error"

        # Check collateral component accuracy
        collateral_scores = result.get("component_scores", {}).get("collateral", {})
        assert collateral_scores, "Should have collateral scores"

        # Target: 90% accuracy for collateral type classification
        avg_score = collateral_scores.get("average_score", 0.0)
        assert avg_score >= 0.90, \
            f"Collateral type classification accuracy {avg_score} below 90%"

    def test_temporal_normalization_accuracy(self, validator, sample_normalized):
        """Test accuracy of temporal field normalization."""
        result = validator.validate_normalization(
            document_id="csa_credit_suisse",
            normalized_data=sample_normalized
        )

        assert not result.get("error"), "Validation should not error"

        # Check temporal component accuracy
        temporal_scores = result.get("component_scores", {}).get("temporal", {})
        assert temporal_scores, "Should have temporal scores"

        # Temporal fields should have high accuracy
        for field, score in temporal_scores.items():
            assert score >= 0.85, \
                f"Temporal field '{field}' accuracy {score} below 85%"

    def test_currency_normalization_accuracy(self, validator, sample_normalized):
        """Test accuracy of currency field normalization."""
        result = validator.validate_normalization(
            document_id="csa_credit_suisse",
            normalized_data=sample_normalized
        )

        assert not result.get("error"), "Validation should not error"

        # Check currency component accuracy
        currency_scores = result.get("component_scores", {}).get("currency", {})
        assert currency_scores, "Should have currency scores"

        # Currency normalization should be very accurate (rule-based)
        for field, score in currency_scores.items():
            assert score >= 0.95, \
                f"Currency field '{field}' accuracy {score} below 95%"

    def test_overall_normalization_accuracy_threshold(self, validator, sample_normalized):
        """Test that overall normalization accuracy meets minimum threshold."""
        result = validator.validate_normalization(
            document_id="csa_credit_suisse",
            normalized_data=sample_normalized
        )

        assert not result.get("error"), "Validation should not error"

        overall_metrics = result.get("overall_metrics", {})
        accuracy = overall_metrics.get("accuracy", 0.0)

        # Target: 90% overall accuracy for normalization
        assert accuracy >= 0.90, \
            f"Overall normalization accuracy {accuracy} below target 90%"

    def test_confidence_meets_thresholds(self, validator, sample_normalized):
        """Test that confidence scores meet minimum thresholds."""
        result = validator.validate_normalization(
            document_id="csa_credit_suisse",
            normalized_data=sample_normalized
        )

        assert not result.get("error"), "Validation should not error"

        # Check confidence validation
        confidence_checks = result.get("confidence_checks", {})

        # All confidence checks should pass
        for check_name, passed in confidence_checks.items():
            assert passed, f"Confidence check '{check_name}' failed"

    def test_maturity_bucket_accuracy(self, validator, sample_normalized):
        """Test accuracy of maturity bucket parsing."""
        # Add normalized data with maturity buckets
        sample_with_buckets = sample_normalized.copy()
        sample_with_buckets["normalized_collateral"] = [
            {
                "standardized_type": "US_TREASURY",
                "maturity_buckets": [
                    {
                        "min_maturity_years": 1.0,
                        "max_maturity_years": 2.0,
                        "valuation_percentage": 99.0,
                        "haircut_percentage": 1.0
                    },
                    {
                        "min_maturity_years": 2.0,
                        "max_maturity_years": 3.0,
                        "valuation_percentage": 98.0,
                        "haircut_percentage": 2.0
                    }
                ],
                "confidence": 0.90
            }
        ]

        result = validator.validate_normalization(
            document_id="csa_credit_suisse",
            normalized_data=sample_with_buckets
        )

        # Should not have overlapping bucket errors
        errors = result.get("errors", [])
        overlap_errors = [
            e for e in errors
            if "overlap" in e.get("message", "").lower()
        ]

        assert len(overlap_errors) == 0, \
            "Maturity buckets should not have overlaps"


class TestAggregateAccuracy:
    """Test aggregate accuracy across multiple documents."""

    @pytest.fixture
    def validator(self):
        """Create accuracy validator instance."""
        return AccuracyValidator()

    def test_aggregate_accuracy_calculation(self):
        """Test aggregate accuracy calculation across multiple results."""
        # Sample validation results
        results = [
            {
                "document_id": "doc1",
                "passed": True,
                "overall_metrics": {
                    "precision": 0.95,
                    "recall": 0.93,
                    "accuracy": 0.94,
                    "true_positives": 19,
                    "false_positives": 1,
                    "false_negatives": 2,
                    "total_fields": 20
                }
            },
            {
                "document_id": "doc2",
                "passed": True,
                "overall_metrics": {
                    "precision": 0.97,
                    "recall": 0.96,
                    "accuracy": 0.96,
                    "true_positives": 24,
                    "false_positives": 1,
                    "false_negatives": 1,
                    "total_fields": 25
                }
            }
        ]

        aggregate = calculate_aggregate_accuracy(results)

        assert aggregate.get("total_documents") == 2
        assert aggregate.get("documents_passed") == 2
        assert aggregate.get("pass_rate") == 1.0

        agg_metrics = aggregate.get("aggregate_metrics", {})
        assert agg_metrics.get("true_positives") == 43  # 19 + 24
        assert agg_metrics.get("total_fields") == 45  # 20 + 25

    def test_pass_rate_calculation(self):
        """Test pass rate calculation."""
        results = [
            {"passed": True, "overall_metrics": {"true_positives": 10, "false_positives": 0, "false_negatives": 0, "total_fields": 10}},
            {"passed": True, "overall_metrics": {"true_positives": 8, "false_positives": 1, "false_negatives": 1, "total_fields": 10}},
            {"passed": False, "overall_metrics": {"true_positives": 5, "false_positives": 3, "false_negatives": 2, "total_fields": 10}}
        ]

        aggregate = calculate_aggregate_accuracy(results)

        # 2 out of 3 passed
        assert aggregate.get("pass_rate") == pytest.approx(0.667, abs=0.01)
        assert aggregate.get("documents_passed") == 2
        assert aggregate.get("documents_failed") == 1


class TestErrorAnalysis:
    """Test error pattern detection and analysis."""

    @pytest.fixture
    def validator(self):
        """Create accuracy validator instance."""
        return AccuracyValidator()

    def test_error_categorization(self, validator):
        """Test that errors are properly categorized."""
        # Sample data with intentional errors
        extracted = {
            "agreement_info": {
                "agreement_title": "CREDIT SUPPORT ANNEX",  # Missing full title
                # Missing party_a (extraction failure)
                "party_b": "FIFTH THIRD AUTO TRUST 2008-1"
            },
            "core_margin_terms": {
                "party_a_threshold": "Infinity",
                "base_currency": "USD"  # Wrong format, should be "US Dollars"
            }
        }

        result = validator.validate_extraction(
            document_id="csa_credit_suisse",
            extracted_fields=extracted
        )

        errors = result.get("errors", [])
        assert len(errors) > 0, "Should detect errors"

        # Check error types
        error_types = {e.get("type") for e in errors}
        assert "extraction_failure" in error_types, "Should detect missing fields"
        assert "extraction_mismatch" in error_types, "Should detect incorrect values"

    def test_field_level_error_tracking(self, validator):
        """Test that errors are tracked at field level."""
        extracted = {
            "agreement_info": {
                "agreement_title": "Wrong Title",
                "agreement_date": "2008-03-31",  # Different format
                "party_a": "CREDIT SUISSE INTERNATIONAL",
                "party_b": "FIFTH THIRD AUTO TRUST 2008-1"
            }
        }

        result = validator.validate_extraction(
            document_id="csa_credit_suisse",
            extracted_fields=extracted
        )

        errors = result.get("errors", [])

        # Each error should have field information
        for error in errors:
            assert "field" in error, "Error should specify field"
            assert "section" in error, "Error should specify section"
            assert "message" in error, "Error should have message"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
