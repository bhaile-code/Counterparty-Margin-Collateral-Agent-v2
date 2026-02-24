"""
Accuracy Validator Service

Compares extracted and normalized data against ground truth to calculate
accuracy metrics for the document processing pipeline.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import math


class ErrorType(Enum):
    """Categories of errors that can occur during processing."""
    EXTRACTION_FAILURE = "extraction_failure"  # Field not extracted
    EXTRACTION_MISMATCH = "extraction_mismatch"  # Extracted incorrectly
    NORMALIZATION_ERROR = "normalization_error"  # Incorrect normalization
    TYPE_MISMATCH = "type_mismatch"  # Wrong collateral type
    VALUE_MISMATCH = "value_mismatch"  # Wrong numerical value
    CONFIDENCE_TOO_LOW = "confidence_too_low"  # Below minimum threshold


class AccuracyMetrics:
    """Container for accuracy metrics."""

    def __init__(self):
        self.true_positives = 0  # Correctly extracted/normalized
        self.false_positives = 0  # Extracted but incorrect
        self.false_negatives = 0  # Expected but not extracted
        self.total_fields = 0
        self.errors: List[Dict[str, Any]] = []

    @property
    def precision(self) -> float:
        """Precision: TP / (TP + FP)"""
        denominator = self.true_positives + self.false_positives
        return self.true_positives / denominator if denominator > 0 else 0.0

    @property
    def recall(self) -> float:
        """Recall: TP / (TP + FN)"""
        denominator = self.true_positives + self.false_negatives
        return self.true_positives / denominator if denominator > 0 else 0.0

    @property
    def f1_score(self) -> float:
        """F1 Score: Harmonic mean of precision and recall"""
        p = self.precision
        r = self.recall
        return 2 * (p * r) / (p + r) if (p + r) > 0 else 0.0

    @property
    def accuracy(self) -> float:
        """Overall accuracy: TP / Total"""
        return self.true_positives / self.total_fields if self.total_fields > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Error rate: Errors / Total"""
        return len(self.errors) / self.total_fields if self.total_fields > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "accuracy": round(self.accuracy, 4),
            "error_rate": round(self.error_rate, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "total_fields": self.total_fields,
            "error_count": len(self.errors)
        }


class AccuracyValidator:
    """
    Validates extraction and normalization accuracy against ground truth.
    """

    def __init__(self, ground_truth_dir: str = "backend/tests/ground_truth"):
        self.ground_truth_dir = Path(ground_truth_dir)

    def load_ground_truth_extraction(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Load ground truth extraction data for a document."""
        file_path = self.ground_truth_dir / "expected_extractions" / f"{document_id}_extraction.json"
        if not file_path.exists():
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_ground_truth_normalized(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Load ground truth normalization data for a document."""
        file_path = self.ground_truth_dir / "expected_normalized" / f"{document_id}_normalized.json"
        if not file_path.exists():
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def validate_extraction(
        self,
        document_id: str,
        extracted_fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate extraction accuracy against ground truth.

        Args:
            document_id: Identifier for the document
            extracted_fields: The extracted fields from ADE

        Returns:
            Dictionary containing accuracy metrics and detailed error report
        """
        ground_truth = self.load_ground_truth_extraction(document_id)
        if not ground_truth:
            return {
                "error": f"No ground truth found for document_id: {document_id}",
                "available": False
            }

        expected = ground_truth.get("expected_fields", {})
        metrics = AccuracyMetrics()

        # Validate each section
        field_scores = {}

        # Agreement Info
        if "agreement_info" in expected:
            field_scores["agreement_info"] = self._compare_dict_fields(
                "agreement_info",
                expected["agreement_info"],
                extracted_fields.get("agreement_info", {}),
                metrics
            )

        # Core Margin Terms
        if "core_margin_terms" in expected:
            field_scores["core_margin_terms"] = self._compare_dict_fields(
                "core_margin_terms",
                expected["core_margin_terms"],
                extracted_fields.get("core_margin_terms", {}),
                metrics
            )

        # Valuation Timing
        if "valuation_timing" in expected:
            field_scores["valuation_timing"] = self._compare_dict_fields(
                "valuation_timing",
                expected["valuation_timing"],
                extracted_fields.get("valuation_timing", {}),
                metrics
            )

        # Eligible Collateral Table (special handling for arrays)
        if "eligible_collateral_table" in expected:
            field_scores["eligible_collateral_table"] = self._compare_collateral_table(
                expected["eligible_collateral_table"],
                extracted_fields.get("eligible_collateral_table", []),
                metrics
            )

        return {
            "document_id": document_id,
            "overall_metrics": metrics.to_dict(),
            "field_scores": field_scores,
            "errors": metrics.errors,
            "passed": metrics.accuracy >= 0.95  # 95% accuracy threshold
        }

    def validate_normalization(
        self,
        document_id: str,
        normalized_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate normalization accuracy against ground truth.

        Args:
            document_id: Identifier for the document
            normalized_data: The normalized multi-agent output

        Returns:
            Dictionary containing accuracy metrics and detailed error report
        """
        ground_truth = self.load_ground_truth_normalized(document_id)
        if not ground_truth:
            return {
                "error": f"No ground truth found for document_id: {document_id}",
                "available": False
            }

        metrics = AccuracyMetrics()
        component_scores = {}

        # Validate normalized collateral
        if "expected_normalized_collateral" in ground_truth:
            component_scores["collateral"] = self._validate_normalized_collateral(
                ground_truth["expected_normalized_collateral"],
                normalized_data.get("normalized_collateral", []),
                metrics
            )

        # Validate temporal normalization
        if "expected_temporal" in ground_truth:
            component_scores["temporal"] = self._validate_temporal(
                ground_truth["expected_temporal"],
                normalized_data.get("temporal", {}),
                metrics
            )

        # Validate currency normalization
        if "expected_currency" in ground_truth:
            component_scores["currency"] = self._validate_currency(
                ground_truth["expected_currency"],
                normalized_data.get("currency", {}),
                metrics
            )

        # Check confidence levels
        confidence_checks = self._validate_confidence_levels(
            ground_truth,
            normalized_data,
            metrics
        )

        return {
            "document_id": document_id,
            "overall_metrics": metrics.to_dict(),
            "component_scores": component_scores,
            "confidence_checks": confidence_checks,
            "errors": metrics.errors,
            "passed": metrics.accuracy >= 0.90  # 90% accuracy threshold for normalization
        }

    def _compare_dict_fields(
        self,
        section_name: str,
        expected: Dict[str, Any],
        actual: Dict[str, Any],
        metrics: AccuracyMetrics
    ) -> Dict[str, float]:
        """Compare dictionary fields and update metrics."""
        field_results = {}

        for field_name, expected_value in expected.items():
            metrics.total_fields += 1
            actual_value = actual.get(field_name)

            if actual_value is None:
                # Field not extracted
                metrics.false_negatives += 1
                metrics.errors.append({
                    "type": ErrorType.EXTRACTION_FAILURE.value,
                    "section": section_name,
                    "field": field_name,
                    "expected": expected_value,
                    "actual": None,
                    "message": f"Field '{field_name}' not extracted"
                })
                field_results[field_name] = 0.0
            elif self._values_match(expected_value, actual_value):
                # Correct extraction
                metrics.true_positives += 1
                field_results[field_name] = 1.0
            else:
                # Incorrect extraction
                metrics.false_positives += 1
                similarity = self._calculate_similarity(expected_value, actual_value)
                field_results[field_name] = similarity

                if similarity < 0.8:  # Only log significant mismatches
                    metrics.errors.append({
                        "type": ErrorType.EXTRACTION_MISMATCH.value,
                        "section": section_name,
                        "field": field_name,
                        "expected": expected_value,
                        "actual": actual_value,
                        "similarity": similarity,
                        "message": f"Field '{field_name}' mismatch"
                    })

        return field_results

    def _compare_collateral_table(
        self,
        expected: List[Dict[str, Any]],
        actual: List[Dict[str, Any]],
        metrics: AccuracyMetrics
    ) -> Dict[str, Any]:
        """Compare collateral table arrays."""
        results = {
            "row_count_match": len(expected) == len(actual),
            "expected_rows": len(expected),
            "actual_rows": len(actual),
            "row_matches": []
        }

        for i, expected_row in enumerate(expected):
            metrics.total_fields += 1

            if i >= len(actual):
                metrics.false_negatives += 1
                metrics.errors.append({
                    "type": ErrorType.EXTRACTION_FAILURE.value,
                    "section": "eligible_collateral_table",
                    "field": f"row_{i}",
                    "expected": expected_row,
                    "actual": None,
                    "message": f"Collateral row {i} not extracted"
                })
                results["row_matches"].append(0.0)
                continue

            actual_row = actual[i]

            # Extract nested structure if present
            expected_data = expected_row.get("eligible_collateral_row", expected_row)
            actual_data = actual_row.get("eligible_collateral_row", actual_row)

            # Compare collateral type
            type_match = self._values_match(
                expected_data.get("collateral_type", ""),
                actual_data.get("collateral_type", "")
            )

            # Compare valuation percentages
            expected_vals = expected_data.get("valuation_percentages", [])
            actual_vals = actual_data.get("valuation_percentages", [])
            vals_match = expected_vals == actual_vals

            if type_match and vals_match:
                metrics.true_positives += 1
                results["row_matches"].append(1.0)
            else:
                metrics.false_positives += 1
                results["row_matches"].append(0.5 if type_match or vals_match else 0.0)

                metrics.errors.append({
                    "type": ErrorType.EXTRACTION_MISMATCH.value,
                    "section": "eligible_collateral_table",
                    "field": f"row_{i}",
                    "expected": expected_data,
                    "actual": actual_data,
                    "message": f"Collateral row {i} mismatch"
                })

        results["average_match_score"] = (
            sum(results["row_matches"]) / len(results["row_matches"])
            if results["row_matches"] else 0.0
        )

        return results

    def _validate_normalized_collateral(
        self,
        expected: List[Dict[str, Any]],
        actual: List[Dict[str, Any]],
        metrics: AccuracyMetrics
    ) -> Dict[str, Any]:
        """Validate normalized collateral items."""
        results = {
            "item_count_match": len(expected) == len(actual),
            "expected_items": len(expected),
            "actual_items": len(actual),
            "item_scores": []
        }

        for i, expected_item in enumerate(expected):
            if i >= len(actual):
                metrics.total_fields += 1
                metrics.false_negatives += 1
                metrics.errors.append({
                    "type": ErrorType.NORMALIZATION_ERROR.value,
                    "component": "collateral",
                    "field": f"item_{i}",
                    "expected": expected_item,
                    "actual": None,
                    "message": f"Collateral item {i} not normalized"
                })
                results["item_scores"].append(0.0)
                continue

            actual_item = actual[i]
            item_score = self._compare_collateral_item(expected_item, actual_item, metrics)
            results["item_scores"].append(item_score)

        results["average_score"] = (
            sum(results["item_scores"]) / len(results["item_scores"])
            if results["item_scores"] else 0.0
        )

        return results

    def _compare_collateral_item(
        self,
        expected: Dict[str, Any],
        actual: Dict[str, Any],
        metrics: AccuracyMetrics
    ) -> float:
        """Compare a single normalized collateral item."""
        metrics.total_fields += 1
        score = 0.0
        max_score = 3.0  # Type (1) + Buckets (1) + Confidence (1)

        # Check standardized type
        expected_type = expected.get("standardized_type")
        actual_type = actual.get("standardized_type")

        if expected_type == actual_type:
            score += 1.0
        else:
            metrics.errors.append({
                "type": ErrorType.TYPE_MISMATCH.value,
                "component": "collateral",
                "field": "standardized_type",
                "expected": expected_type,
                "actual": actual_type,
                "message": f"Type mismatch: expected {expected_type}, got {actual_type}"
            })

        # Check maturity buckets
        expected_buckets = expected.get("maturity_buckets", [])
        actual_buckets = actual.get("maturity_buckets", [])

        if len(expected_buckets) == len(actual_buckets):
            bucket_matches = sum(
                1 for exp_b, act_b in zip(expected_buckets, actual_buckets)
                if self._buckets_match(exp_b, act_b)
            )
            score += bucket_matches / len(expected_buckets) if expected_buckets else 1.0
        else:
            metrics.errors.append({
                "type": ErrorType.NORMALIZATION_ERROR.value,
                "component": "collateral",
                "field": "maturity_buckets",
                "expected": f"{len(expected_buckets)} buckets",
                "actual": f"{len(actual_buckets)} buckets",
                "message": "Bucket count mismatch"
            })

        # Check confidence level
        min_confidence = expected.get("min_confidence", 0.0)
        actual_confidence = actual.get("confidence", 0.0)

        if actual_confidence >= min_confidence:
            score += 1.0
        else:
            metrics.errors.append({
                "type": ErrorType.CONFIDENCE_TOO_LOW.value,
                "component": "collateral",
                "field": "confidence",
                "expected": f">= {min_confidence}",
                "actual": actual_confidence,
                "message": f"Confidence {actual_confidence} below threshold {min_confidence}"
            })

        final_score = score / max_score

        if final_score >= 0.9:
            metrics.true_positives += 1
        elif final_score >= 0.5:
            metrics.false_positives += 1
        else:
            metrics.false_positives += 1

        return final_score

    def _buckets_match(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
        """Check if two maturity buckets match."""
        return (
            self._floats_match(expected.get("min_maturity_years"), actual.get("min_maturity_years")) and
            self._floats_match(expected.get("max_maturity_years"), actual.get("max_maturity_years")) and
            self._floats_match(expected.get("valuation_percentage"), actual.get("valuation_percentage"), tolerance=0.1) and
            self._floats_match(expected.get("haircut_percentage"), actual.get("haircut_percentage"), tolerance=0.1)
        )

    def _validate_temporal(
        self,
        expected: Dict[str, Any],
        actual: Dict[str, Any],
        metrics: AccuracyMetrics
    ) -> Dict[str, float]:
        """Validate temporal normalization."""
        field_scores = {}

        for field_name, expected_data in expected.items():
            metrics.total_fields += 1
            actual_data = actual.get(field_name, {})

            time_match = expected_data.get("time") == actual_data.get("time")
            tz_match = expected_data.get("timezone") == actual_data.get("timezone")
            conf_ok = actual_data.get("confidence", 0.0) >= expected_data.get("min_confidence", 0.0)

            if time_match and tz_match and conf_ok:
                metrics.true_positives += 1
                field_scores[field_name] = 1.0
            else:
                metrics.false_positives += 1
                score = (int(time_match) + int(tz_match) + int(conf_ok)) / 3.0
                field_scores[field_name] = score

                metrics.errors.append({
                    "type": ErrorType.NORMALIZATION_ERROR.value,
                    "component": "temporal",
                    "field": field_name,
                    "expected": expected_data,
                    "actual": actual_data,
                    "message": f"Temporal field '{field_name}' mismatch"
                })

        return field_scores

    def _validate_currency(
        self,
        expected: Dict[str, Any],
        actual: Dict[str, Any],
        metrics: AccuracyMetrics
    ) -> Dict[str, float]:
        """Validate currency normalization."""
        field_scores = {}

        for field_name, expected_data in expected.items():
            metrics.total_fields += 1
            actual_data = actual.get(field_name, {})

            currency_match = expected_data.get("currency_code") == actual_data.get("currency_code")
            amount_match = self._floats_match(
                expected_data.get("amount"),
                actual_data.get("amount"),
                tolerance=0.01
            )
            conf_ok = actual_data.get("confidence", 0.0) >= expected_data.get("min_confidence", 0.0)

            # Special handling for infinity and not applicable
            if expected_data.get("is_infinity"):
                amount_match = actual_data.get("is_infinity", False)
            if expected_data.get("is_not_applicable"):
                amount_match = actual_data.get("is_not_applicable", False)

            if currency_match and amount_match and conf_ok:
                metrics.true_positives += 1
                field_scores[field_name] = 1.0
            else:
                metrics.false_positives += 1
                score = (int(currency_match) + int(amount_match) + int(conf_ok)) / 3.0
                field_scores[field_name] = score

                metrics.errors.append({
                    "type": ErrorType.NORMALIZATION_ERROR.value,
                    "component": "currency",
                    "field": field_name,
                    "expected": expected_data,
                    "actual": actual_data,
                    "message": f"Currency field '{field_name}' mismatch"
                })

        return field_scores

    def _validate_confidence_levels(
        self,
        ground_truth: Dict[str, Any],
        normalized_data: Dict[str, Any],
        metrics: AccuracyMetrics
    ) -> Dict[str, bool]:
        """Validate that confidence levels meet minimum thresholds."""
        checks = {}

        # Check overall confidence if present
        if "overall_confidence" in normalized_data:
            expected_min = ground_truth.get("min_overall_confidence", 0.80)
            actual = normalized_data["overall_confidence"]
            checks["overall_confidence_ok"] = actual >= expected_min

            if not checks["overall_confidence_ok"]:
                metrics.errors.append({
                    "type": ErrorType.CONFIDENCE_TOO_LOW.value,
                    "component": "overall",
                    "field": "confidence",
                    "expected": f">= {expected_min}",
                    "actual": actual,
                    "message": f"Overall confidence {actual} below threshold {expected_min}"
                })

        return checks

    def _values_match(self, expected: Any, actual: Any, fuzzy: bool = True) -> bool:
        """Check if two values match, with optional fuzzy matching."""
        if expected == actual:
            return True

        if not fuzzy:
            return False

        # Normalize strings for comparison
        if isinstance(expected, str) and isinstance(actual, str):
            # Remove extra whitespace, case-insensitive
            exp_norm = " ".join(expected.lower().split())
            act_norm = " ".join(actual.lower().split())

            # Check for substring match (at least 80% overlap)
            if exp_norm in act_norm or act_norm in exp_norm:
                return True

            # Check similarity
            similarity = self._calculate_similarity(expected, actual)
            return similarity >= 0.8

        return False

    def _calculate_similarity(self, expected: Any, actual: Any) -> float:
        """Calculate similarity score between two values."""
        if expected == actual:
            return 1.0

        if isinstance(expected, str) and isinstance(actual, str):
            # Simple string similarity (Jaccard similarity on words)
            expected_words = set(expected.lower().split())
            actual_words = set(actual.lower().split())

            if not expected_words and not actual_words:
                return 1.0
            if not expected_words or not actual_words:
                return 0.0

            intersection = expected_words & actual_words
            union = expected_words | actual_words

            return len(intersection) / len(union)

        return 0.0

    def _floats_match(
        self,
        expected: Optional[float],
        actual: Optional[float],
        tolerance: float = 0.001
    ) -> bool:
        """Check if two floats match within tolerance."""
        if expected is None and actual is None:
            return True
        if expected is None or actual is None:
            return False

        return abs(expected - actual) <= tolerance


def calculate_aggregate_accuracy(
    validation_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate aggregate accuracy metrics across multiple documents.

    Args:
        validation_results: List of validation result dictionaries

    Returns:
        Aggregate accuracy statistics
    """
    if not validation_results:
        return {"error": "No validation results provided"}

    total_metrics = AccuracyMetrics()

    for result in validation_results:
        if "overall_metrics" in result:
            m = result["overall_metrics"]
            total_metrics.true_positives += m.get("true_positives", 0)
            total_metrics.false_positives += m.get("false_positives", 0)
            total_metrics.false_negatives += m.get("false_negatives", 0)
            total_metrics.total_fields += m.get("total_fields", 0)

    passed_count = sum(1 for r in validation_results if r.get("passed", False))

    return {
        "total_documents": len(validation_results),
        "documents_passed": passed_count,
        "documents_failed": len(validation_results) - passed_count,
        "pass_rate": passed_count / len(validation_results),
        "aggregate_metrics": total_metrics.to_dict()
    }
