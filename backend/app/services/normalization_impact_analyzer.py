"""
Normalization Impact Analyzer

Compares accuracy before normalization (raw extraction) vs. after normalization
to quantify the improvement provided by the multi-agent normalization system.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from .accuracy_validator import AccuracyValidator, AccuracyMetrics


class NormalizationImpact:
    """Container for normalization impact metrics."""

    def __init__(
        self,
        extraction_accuracy: float,
        normalization_accuracy: float,
        improvement_absolute: float,
        improvement_percentage: float,
        extraction_metrics: Dict[str, Any],
        normalization_metrics: Dict[str, Any]
    ):
        self.extraction_accuracy = extraction_accuracy
        self.normalization_accuracy = normalization_accuracy
        self.improvement_absolute = improvement_absolute
        self.improvement_percentage = improvement_percentage
        self.extraction_metrics = extraction_metrics
        self.normalization_metrics = normalization_metrics

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "before_normalization": {
                "accuracy": round(self.extraction_accuracy, 4),
                "metrics": self.extraction_metrics
            },
            "after_normalization": {
                "accuracy": round(self.normalization_accuracy, 4),
                "metrics": self.normalization_metrics
            },
            "improvement": {
                "absolute": round(self.improvement_absolute, 4),
                "percentage": round(self.improvement_percentage, 4),
                "description": self._get_improvement_description()
            },
            "quality_level": self._get_quality_level()
        }

    def _get_improvement_description(self) -> str:
        """Get human-readable description of improvement."""
        if self.improvement_absolute >= 0.20:
            return "Significant improvement - Normalization highly effective"
        elif self.improvement_absolute >= 0.10:
            return "Substantial improvement - Normalization working well"
        elif self.improvement_absolute >= 0.05:
            return "Moderate improvement - Normalization adding value"
        elif self.improvement_absolute >= 0.01:
            return "Minor improvement - Normalization making small corrections"
        elif self.improvement_absolute >= -0.01:
            return "No significant change - Data already well-structured"
        else:
            return "Degradation detected - Review normalization logic"

    def _get_quality_level(self) -> Dict[str, str]:
        """Assess overall quality level."""
        return {
            "before": self._quality_label(self.extraction_accuracy),
            "after": self._quality_label(self.normalization_accuracy)
        }

    def _quality_label(self, accuracy: float) -> str:
        """Get quality label for accuracy score."""
        if accuracy >= 0.95:
            return "Excellent"
        elif accuracy >= 0.90:
            return "Good"
        elif accuracy >= 0.80:
            return "Acceptable"
        elif accuracy >= 0.70:
            return "Poor"
        else:
            return "Inadequate"


class NormalizationImpactAnalyzer:
    """
    Analyzes the impact of normalization on data accuracy.

    Compares:
    - Raw extraction accuracy (before normalization)
    - Normalized data accuracy (after normalization)
    - Calculates improvement metrics
    """

    def __init__(self, ground_truth_dir: str = "backend/tests/ground_truth"):
        self.validator = AccuracyValidator(ground_truth_dir)

    def analyze_impact(
        self,
        document_id: str,
        extraction_data: Dict[str, Any],
        normalized_data: Dict[str, Any]
    ) -> Optional[NormalizationImpact]:
        """
        Analyze normalization impact for a document.

        Args:
            document_id: Document identifier (for ground truth lookup)
            extraction_data: Raw extraction result
            normalized_data: Normalized result from multi-agent system

        Returns:
            NormalizationImpact object with before/after metrics, or None if no ground truth
        """
        # Validate extraction (before normalization)
        extraction_result = self.validator.validate_extraction(
            document_id=document_id,
            extracted_fields=extraction_data
        )

        if extraction_result.get("error"):
            return None  # No ground truth available

        # Validate normalization (after normalization)
        normalization_result = self.validator.validate_normalization(
            document_id=document_id,
            normalized_data=normalized_data
        )

        if normalization_result.get("error"):
            return None  # No ground truth available

        # Extract accuracy scores
        extraction_accuracy = extraction_result["overall_metrics"]["accuracy"]
        normalization_accuracy = normalization_result["overall_metrics"]["accuracy"]

        # Calculate improvement
        improvement_absolute = normalization_accuracy - extraction_accuracy
        improvement_percentage = (
            (improvement_absolute / extraction_accuracy * 100)
            if extraction_accuracy > 0 else 0
        )

        return NormalizationImpact(
            extraction_accuracy=extraction_accuracy,
            normalization_accuracy=normalization_accuracy,
            improvement_absolute=improvement_absolute,
            improvement_percentage=improvement_percentage,
            extraction_metrics=extraction_result["overall_metrics"],
            normalization_metrics=normalization_result["overall_metrics"]
        )

    def analyze_field_level_impact(
        self,
        document_id: str,
        extraction_data: Dict[str, Any],
        normalized_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze normalization impact at field level.

        Shows which specific fields improved the most during normalization.

        Returns:
            Dictionary with field-level improvement metrics
        """
        # Validate both stages
        extraction_result = self.validator.validate_extraction(
            document_id=document_id,
            extracted_fields=extraction_data
        )

        normalization_result = self.validator.validate_normalization(
            document_id=document_id,
            normalized_data=normalized_data
        )

        if extraction_result.get("error") or normalization_result.get("error"):
            return None

        # Compare field scores
        field_improvements = {}

        # For extracted fields that were normalized
        extraction_scores = extraction_result.get("field_scores", {})
        normalization_scores = normalization_result.get("component_scores", {})

        # Currency fields (direct comparison)
        if "currency" in normalization_scores:
            currency_before = extraction_scores.get("core_margin_terms", {})
            currency_after = normalization_scores.get("currency", {})

            for field in ["base_currency"]:
                before = currency_before.get(field, 0.0) if isinstance(currency_before, dict) else 0.0
                after = currency_after.get(field, 0.0) if isinstance(currency_after, dict) else 0.0

                if before != after:
                    field_improvements[f"currency.{field}"] = {
                        "before": round(before, 4),
                        "after": round(after, 4),
                        "improvement": round(after - before, 4)
                    }

        # Temporal fields
        if "temporal" in normalization_scores:
            temporal_before = extraction_scores.get("valuation_timing", {})
            temporal_after = normalization_scores.get("temporal", {})

            for field in temporal_after:
                before = temporal_before.get(field, 0.0) if isinstance(temporal_before, dict) else 0.0
                after = temporal_after.get(field, 0.0) if isinstance(temporal_after, dict) else 0.0

                if before != after:
                    field_improvements[f"temporal.{field}"] = {
                        "before": round(before, 4),
                        "after": round(after, 4),
                        "improvement": round(after - before, 4)
                    }

        # Collateral fields
        if "collateral" in normalization_scores:
            collateral_before_raw = extraction_scores.get("eligible_collateral_table", {})
            collateral_after = normalization_scores.get("collateral", {})

            # Get average scores
            if isinstance(collateral_before_raw, dict):
                before_avg = collateral_before_raw.get("average_match_score", 0.0)
            else:
                before_avg = 0.0

            if isinstance(collateral_after, dict):
                after_avg = collateral_after.get("average_score", 0.0)
            else:
                after_avg = 0.0

            if before_avg != after_avg:
                field_improvements["collateral.overall"] = {
                    "before": round(before_avg, 4),
                    "after": round(after_avg, 4),
                    "improvement": round(after_avg - before_avg, 4)
                }

        # Sort by improvement (largest first)
        sorted_improvements = dict(sorted(
            field_improvements.items(),
            key=lambda x: x[1]["improvement"],
            reverse=True
        ))

        return {
            "field_improvements": sorted_improvements,
            "most_improved": list(sorted_improvements.keys())[:5] if sorted_improvements else [],
            "degraded_fields": [
                field for field, data in sorted_improvements.items()
                if data["improvement"] < 0
            ]
        }

    def generate_comparison_report(
        self,
        document_id: str,
        extraction_data: Dict[str, Any],
        normalized_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate comprehensive comparison report.

        Args:
            document_id: Document identifier
            extraction_data: Raw extraction result
            normalized_data: Normalized result

        Returns:
            Full comparison report with metrics and recommendations
        """
        impact = self.analyze_impact(document_id, extraction_data, normalized_data)
        if not impact:
            return None

        field_impact = self.analyze_field_level_impact(
            document_id, extraction_data, normalized_data
        )

        # Calculate processing value
        processing_value = self._assess_processing_value(impact)

        # Generate recommendations
        recommendations = self._generate_recommendations(impact, field_impact)

        return {
            "document_id": document_id,
            "overall_impact": impact.to_dict(),
            "field_level_impact": field_impact,
            "processing_value": processing_value,
            "recommendations": recommendations,
            "summary": {
                "before_quality": impact._quality_label(impact.extraction_accuracy),
                "after_quality": impact._quality_label(impact.normalization_accuracy),
                "improvement_description": impact._get_improvement_description(),
                "normalization_effective": impact.improvement_absolute >= 0.05
            }
        }

    def _assess_processing_value(self, impact: NormalizationImpact) -> Dict[str, Any]:
        """
        Assess the value added by normalization processing.

        Considers:
        - Accuracy improvement
        - Processing time/cost
        - Human review reduction
        """
        improvement = impact.improvement_absolute

        if improvement >= 0.10:
            value = "High"
            justification = "Normalization significantly improves data quality"
        elif improvement >= 0.05:
            value = "Medium"
            justification = "Normalization provides measurable improvement"
        elif improvement >= 0.01:
            value = "Low"
            justification = "Normalization provides minimal improvement"
        else:
            value = "Questionable"
            justification = "Normalization may not justify processing cost"

        return {
            "value_rating": value,
            "justification": justification,
            "improvement_score": round(improvement, 4),
            "worth_processing": improvement >= 0.03  # 3% threshold
        }

    def _generate_recommendations(
        self,
        impact: NormalizationImpact,
        field_impact: Optional[Dict[str, Any]]
    ) -> list:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # Overall accuracy recommendations
        if impact.normalization_accuracy < 0.90:
            recommendations.append({
                "priority": "high",
                "category": "accuracy",
                "message": "Overall accuracy below 90% - review normalization agents",
                "action": "Investigate normalization logic and agent prompts"
            })

        if impact.improvement_absolute < 0.01:
            recommendations.append({
                "priority": "medium",
                "category": "efficiency",
                "message": "Minimal improvement from normalization",
                "action": "Consider simplifying normalization pipeline to reduce cost"
            })

        if impact.improvement_absolute < -0.05:
            recommendations.append({
                "priority": "critical",
                "category": "quality",
                "message": "Normalization degrading data quality",
                "action": "Immediately review and fix normalization agents"
            })

        # Field-level recommendations
        if field_impact and field_impact.get("degraded_fields"):
            degraded = field_impact["degraded_fields"]
            recommendations.append({
                "priority": "high",
                "category": "field_quality",
                "message": f"Normalization degrading {len(degraded)} fields",
                "action": f"Review normalization for: {', '.join(degraded)}",
                "affected_fields": degraded
            })

        # Success recommendations
        if impact.improvement_absolute >= 0.10:
            recommendations.append({
                "priority": "low",
                "category": "success",
                "message": "Normalization highly effective",
                "action": "Continue current approach, consider applying to more documents"
            })

        return recommendations


def calculate_aggregate_normalization_impact(
    analyzer: NormalizationImpactAnalyzer,
    documents: list
) -> Dict[str, Any]:
    """
    Calculate aggregate normalization impact across multiple documents.

    Args:
        analyzer: NormalizationImpactAnalyzer instance
        documents: List of dicts with {document_id, extraction_data, normalized_data}

    Returns:
        Aggregate impact statistics
    """
    impacts = []

    for doc in documents:
        impact = analyzer.analyze_impact(
            document_id=doc["document_id"],
            extraction_data=doc["extraction_data"],
            normalized_data=doc["normalized_data"]
        )

        if impact:
            impacts.append(impact)

    if not impacts:
        return {"error": "No impacts calculated"}

    # Calculate averages
    avg_extraction_accuracy = sum(i.extraction_accuracy for i in impacts) / len(impacts)
    avg_normalization_accuracy = sum(i.normalization_accuracy for i in impacts) / len(impacts)
    avg_improvement = sum(i.improvement_absolute for i in impacts) / len(impacts)

    # Count quality levels
    quality_before = {}
    quality_after = {}

    for impact in impacts:
        before_label = impact._quality_label(impact.extraction_accuracy)
        after_label = impact._quality_label(impact.normalization_accuracy)

        quality_before[before_label] = quality_before.get(before_label, 0) + 1
        quality_after[after_label] = quality_after.get(after_label, 0) + 1

    return {
        "total_documents": len(impacts),
        "average_metrics": {
            "before_normalization": round(avg_extraction_accuracy, 4),
            "after_normalization": round(avg_normalization_accuracy, 4),
            "average_improvement": round(avg_improvement, 4)
        },
        "quality_distribution": {
            "before": quality_before,
            "after": quality_after
        },
        "effectiveness": {
            "documents_improved": sum(1 for i in impacts if i.improvement_absolute > 0),
            "documents_degraded": sum(1 for i in impacts if i.improvement_absolute < 0),
            "documents_unchanged": sum(1 for i in impacts if abs(i.improvement_absolute) < 0.01),
            "improvement_rate": sum(1 for i in impacts if i.improvement_absolute > 0) / len(impacts)
        }
    }
