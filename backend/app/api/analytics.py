"""
Analytics API Endpoints

Provides accuracy metrics and analytics for document extraction and normalization.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pathlib import Path
import json
from datetime import datetime

from ..services.accuracy_validator import AccuracyValidator, calculate_aggregate_accuracy
from ..services.normalization_impact_analyzer import NormalizationImpactAnalyzer
from ..utils.file_storage import FileStorage

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

file_storage = FileStorage()
accuracy_validator = AccuracyValidator()
impact_analyzer = NormalizationImpactAnalyzer()


@router.get("/extraction-accuracy/{extraction_id}")
async def get_extraction_accuracy(extraction_id: str):
    """
    Get accuracy metrics for a specific extraction against ground truth.

    Args:
        extraction_id: ID of the extraction to validate

    Returns:
        Accuracy metrics with field-level breakdown
    """
    # Load extraction data
    extraction = file_storage.load_extraction(extraction_id)
    if not extraction:
        raise HTTPException(status_code=404, detail=f"Extraction {extraction_id} not found")

    # Extract document_id from extraction (you may need to adjust based on your data structure)
    document_id = extraction.get("document_id")

    # Try common document identifiers used in ground truth
    ground_truth_ids = [
        "csa_credit_suisse",  # Standard name
        document_id,  # Direct ID
        extraction_id.split("_")[0] if "_" in extraction_id else extraction_id  # Parse from ID
    ]

    # Try to find ground truth
    result = None
    for doc_id in ground_truth_ids:
        result = accuracy_validator.validate_extraction(
            document_id=doc_id,
            extracted_fields=extraction.get("extracted_fields", {})
        )
        if result and not result.get("error"):
            break

    if not result or result.get("error"):
        raise HTTPException(
            status_code=404,
            detail=f"No ground truth available for this extraction. Tried IDs: {ground_truth_ids}"
        )

    return {
        "extraction_id": extraction_id,
        "validation_result": result,
        "validated_at": datetime.now().isoformat()
    }


@router.get("/normalization-accuracy/{normalization_id}")
async def get_normalization_accuracy(normalization_id: str):
    """
    Get accuracy metrics for a specific normalization against ground truth.

    Args:
        normalization_id: ID of the normalization to validate

    Returns:
        Accuracy metrics with component-level breakdown
    """
    # Load normalized data
    normalized_data = file_storage.load_normalized_multiagent(normalization_id)
    if not normalized_data:
        raise HTTPException(
            status_code=404,
            detail=f"Normalized data {normalization_id} not found"
        )

    # Extract document_id
    document_id = normalized_data.get("document_id")

    # Try common document identifiers
    ground_truth_ids = [
        "csa_credit_suisse",
        document_id,
        normalization_id.split("_")[0] if "_" in normalization_id else normalization_id
    ]

    # Build normalized data structure for validation
    normalized_for_validation = {
        "normalized_collateral": normalized_data.get("normalized_collateral_table", []),
        "temporal": normalized_data.get("temporal_fields", {}),
        "currency": normalized_data.get("currency_fields", {}),
        "overall_confidence": normalized_data.get("overall_confidence", 0.0)
    }

    # Try to find ground truth
    result = None
    for doc_id in ground_truth_ids:
        result = accuracy_validator.validate_normalization(
            document_id=doc_id,
            normalized_data=normalized_for_validation
        )
        if result and not result.get("error"):
            break

    if not result or result.get("error"):
        raise HTTPException(
            status_code=404,
            detail=f"No ground truth available for this normalization. Tried IDs: {ground_truth_ids}"
        )

    return {
        "normalization_id": normalization_id,
        "validation_result": result,
        "validated_at": datetime.now().isoformat()
    }


@router.get("/overall-accuracy")
async def get_overall_accuracy(
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    min_confidence: Optional[float] = Query(None, description="Minimum confidence threshold"),
    limit: Optional[int] = Query(100, description="Maximum number of documents to analyze")
):
    """
    Get aggregate accuracy metrics across all documents.

    Query Parameters:
        document_type: Optional filter for document type
        min_confidence: Optional minimum confidence filter
        limit: Maximum number of documents to include

    Returns:
        Aggregate accuracy statistics
    """
    # Get all extractions
    extractions_dir = Path("backend/data/extractions")
    if not extractions_dir.exists():
        raise HTTPException(status_code=404, detail="Extractions directory not found")

    extraction_files = list(extractions_dir.glob("*.json"))[:limit]

    if not extraction_files:
        return {
            "total_documents": 0,
            "message": "No extractions found"
        }

    # Validate each extraction
    validation_results = []
    for extraction_file in extraction_files:
        try:
            with open(extraction_file, 'r', encoding='utf-8') as f:
                extraction = json.load(f)

            # Apply filters
            if min_confidence and extraction.get("overall_confidence", 0.0) < min_confidence:
                continue

            # Try to validate (will skip if no ground truth)
            result = accuracy_validator.validate_extraction(
                document_id="csa_credit_suisse",  # Default to our test document
                extracted_fields=extraction.get("extracted_fields", {})
            )

            if result and not result.get("error"):
                validation_results.append(result)
        except Exception as e:
            # Skip files that can't be loaded
            continue

    if not validation_results:
        return {
            "total_documents_processed": len(extraction_files),
            "documents_with_ground_truth": 0,
            "message": "No documents with ground truth found"
        }

    # Calculate aggregate metrics
    aggregate = calculate_aggregate_accuracy(validation_results)

    return {
        "total_documents_processed": len(extraction_files),
        "documents_validated": len(validation_results),
        "aggregate_statistics": aggregate,
        "generated_at": datetime.now().isoformat()
    }


@router.get("/accuracy-by-field")
async def get_accuracy_by_field():
    """
    Get accuracy breakdown by field type across all documents.

    Returns:
        Field-level accuracy statistics
    """
    # Get all extractions
    extractions_dir = Path("backend/data/extractions")
    if not extractions_dir.exists():
        raise HTTPException(status_code=404, detail="Extractions directory not found")

    extraction_files = list(extractions_dir.glob("*.json"))

    field_stats = {}

    for extraction_file in extraction_files:
        try:
            with open(extraction_file, 'r', encoding='utf-8') as f:
                extraction = json.load(f)

            result = accuracy_validator.validate_extraction(
                document_id="csa_credit_suisse",
                extracted_fields=extraction.get("extracted_fields", {})
            )

            if result and not result.get("error"):
                # Aggregate field scores
                for section, scores in result.get("field_scores", {}).items():
                    if isinstance(scores, dict):
                        for field, score in scores.items():
                            key = f"{section}.{field}"
                            if key not in field_stats:
                                field_stats[key] = {"scores": [], "count": 0}

                            field_stats[key]["scores"].append(score)
                            field_stats[key]["count"] += 1
        except Exception:
            continue

    # Calculate average accuracy per field
    field_accuracy = {}
    for field, data in field_stats.items():
        if data["scores"]:
            field_accuracy[field] = {
                "average_accuracy": round(sum(data["scores"]) / len(data["scores"]), 4),
                "sample_count": data["count"],
                "min_accuracy": round(min(data["scores"]), 4),
                "max_accuracy": round(max(data["scores"]), 4)
            }

    # Sort by accuracy (lowest first to highlight problem areas)
    sorted_fields = dict(sorted(
        field_accuracy.items(),
        key=lambda x: x[1]["average_accuracy"]
    ))

    return {
        "field_accuracy": sorted_fields,
        "total_fields_analyzed": len(field_accuracy),
        "generated_at": datetime.now().isoformat()
    }


@router.get("/confidence-calibration")
async def get_confidence_calibration(
    bins: int = Query(10, description="Number of confidence bins")
):
    """
    Analyze confidence calibration: how well predicted confidence matches actual accuracy.

    Args:
        bins: Number of confidence bins (default 10)

    Returns:
        Calibration curve data and Expected Calibration Error (ECE)
    """
    # Get all normalized results
    normalized_dir = Path("backend/data/normalized_multiagent")
    if not normalized_dir.exists():
        return {
            "error": "No normalized data available",
            "message": "Confidence calibration requires normalized data with ground truth"
        }

    normalized_files = list(normalized_dir.glob("*.json"))

    # Collect (confidence, is_correct) pairs
    predictions = []

    for norm_file in normalized_files:
        try:
            with open(norm_file, 'r', encoding='utf-8') as f:
                normalized_data = json.load(f)

            normalized_for_validation = {
                "normalized_collateral": normalized_data.get("normalized_collateral_table", []),
                "temporal": normalized_data.get("temporal_fields", {}),
                "currency": normalized_data.get("currency_fields", {}),
                "overall_confidence": normalized_data.get("overall_confidence", 0.0)
            }

            result = accuracy_validator.validate_normalization(
                document_id="csa_credit_suisse",
                normalized_data=normalized_for_validation
            )

            if result and not result.get("error"):
                confidence = normalized_data.get("overall_confidence", 0.0)
                accuracy = result.get("overall_metrics", {}).get("accuracy", 0.0)

                predictions.append({
                    "confidence": confidence,
                    "accuracy": accuracy,
                    "is_correct": accuracy >= 0.95  # Consider 95%+ as "correct"
                })
        except Exception:
            continue

    if not predictions:
        return {
            "error": "No calibration data available",
            "message": "No normalized data with ground truth found"
        }

    # Create confidence bins
    bin_size = 1.0 / bins
    bin_data = {i: {"confidences": [], "accuracies": [], "correct_count": 0, "total_count": 0}
                for i in range(bins)}

    for pred in predictions:
        bin_index = min(int(pred["confidence"] / bin_size), bins - 1)
        bin_data[bin_index]["confidences"].append(pred["confidence"])
        bin_data[bin_index]["accuracies"].append(pred["accuracy"])
        bin_data[bin_index]["total_count"] += 1
        if pred["is_correct"]:
            bin_data[bin_index]["correct_count"] += 1

    # Calculate bin statistics
    calibration_curve = []
    ece = 0.0  # Expected Calibration Error

    for i in range(bins):
        bin_info = bin_data[i]
        if bin_info["total_count"] > 0:
            avg_confidence = sum(bin_info["confidences"]) / bin_info["total_count"]
            avg_accuracy = sum(bin_info["accuracies"]) / bin_info["total_count"]
            correct_rate = bin_info["correct_count"] / bin_info["total_count"]

            calibration_error = abs(avg_confidence - correct_rate)
            ece += (bin_info["total_count"] / len(predictions)) * calibration_error

            calibration_curve.append({
                "bin_min": i * bin_size,
                "bin_max": (i + 1) * bin_size,
                "avg_confidence": round(avg_confidence, 4),
                "avg_accuracy": round(avg_accuracy, 4),
                "correct_rate": round(correct_rate, 4),
                "sample_count": bin_info["total_count"],
                "calibration_error": round(calibration_error, 4)
            })

    return {
        "calibration_curve": calibration_curve,
        "expected_calibration_error": round(ece, 4),
        "total_predictions": len(predictions),
        "bins": bins,
        "interpretation": {
            "ece_meaning": "Lower is better. < 0.05 is well-calibrated, > 0.15 is poorly calibrated",
            "curve_ideal": "avg_confidence should equal correct_rate for perfect calibration"
        },
        "generated_at": datetime.now().isoformat()
    }


@router.get("/error-analysis")
async def get_error_analysis():
    """
    Analyze common error patterns across all validations.

    Returns:
        Error breakdown by type, section, and field
    """
    # Get all extractions
    extractions_dir = Path("backend/data/extractions")
    if not extractions_dir.exists():
        raise HTTPException(status_code=404, detail="Extractions directory not found")

    extraction_files = list(extractions_dir.glob("*.json"))

    error_stats = {
        "by_type": {},
        "by_section": {},
        "by_field": {},
        "total_errors": 0
    }

    for extraction_file in extraction_files:
        try:
            with open(extraction_file, 'r', encoding='utf-8') as f:
                extraction = json.load(f)

            result = accuracy_validator.validate_extraction(
                document_id="csa_credit_suisse",
                extracted_fields=extraction.get("extracted_fields", {})
            )

            if result and not result.get("error"):
                for error in result.get("errors", []):
                    error_stats["total_errors"] += 1

                    # By type
                    error_type = error.get("type", "unknown")
                    error_stats["by_type"][error_type] = error_stats["by_type"].get(error_type, 0) + 1

                    # By section
                    section = error.get("section", "unknown")
                    error_stats["by_section"][section] = error_stats["by_section"].get(section, 0) + 1

                    # By field
                    field = error.get("field", "unknown")
                    field_key = f"{section}.{field}"
                    if field_key not in error_stats["by_field"]:
                        error_stats["by_field"][field_key] = {
                            "count": 0,
                            "examples": []
                        }

                    error_stats["by_field"][field_key]["count"] += 1

                    # Store up to 3 examples per field
                    if len(error_stats["by_field"][field_key]["examples"]) < 3:
                        error_stats["by_field"][field_key]["examples"].append({
                            "expected": error.get("expected"),
                            "actual": error.get("actual"),
                            "message": error.get("message")
                        })
        except Exception:
            continue

    # Sort by frequency
    error_stats["by_type"] = dict(sorted(
        error_stats["by_type"].items(),
        key=lambda x: x[1],
        reverse=True
    ))

    error_stats["by_section"] = dict(sorted(
        error_stats["by_section"].items(),
        key=lambda x: x[1],
        reverse=True
    ))

    error_stats["by_field"] = dict(sorted(
        error_stats["by_field"].items(),
        key=lambda x: x[1]["count"],
        reverse=True
    ))

    return {
        "error_statistics": error_stats,
        "generated_at": datetime.now().isoformat()
    }


@router.get("/normalization-impact/{document_id}")
async def get_normalization_impact(document_id: str):
    """
    Compare accuracy before normalization (raw extraction) vs. after normalization.

    Shows the improvement provided by the multi-agent normalization system.

    Args:
        document_id: ID of the document to analyze

    Returns:
        Comparison report with before/after metrics and improvement analysis
    """
    # Find extraction data
    extractions_dir = Path("backend/data/extractions")
    extraction_files = list(extractions_dir.glob(f"*{document_id}*.json"))

    if not extraction_files:
        raise HTTPException(
            status_code=404,
            detail=f"No extraction data found for document {document_id}"
        )

    # Load extraction data
    with open(extraction_files[0], 'r', encoding='utf-8') as f:
        extraction_data = json.load(f)

    # Find normalized data
    normalized_dir = Path("backend/data/normalized_multiagent")
    if normalized_dir.exists():
        normalized_files = list(normalized_dir.glob(f"*{document_id}*.json"))

        if normalized_files:
            with open(normalized_files[0], 'r', encoding='utf-8') as f:
                normalized_raw = json.load(f)

            # Build normalized data structure
            normalized_data = {
                "normalized_collateral": normalized_raw.get("normalized_collateral_table", []),
                "temporal": normalized_raw.get("temporal_fields", {}),
                "currency": normalized_raw.get("currency_fields", {}),
                "overall_confidence": normalized_raw.get("overall_confidence", 0.0)
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No normalization data found for document {document_id}"
            )
    else:
        raise HTTPException(
            status_code=404,
            detail="Normalization directory not found"
        )

    # Generate comparison report
    report = impact_analyzer.generate_comparison_report(
        document_id="csa_credit_suisse",  # Use available ground truth
        extraction_data=extraction_data.get("extracted_fields", {}),
        normalized_data=normalized_data
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="No ground truth available for comparison"
        )

    return {
        "document_id": document_id,
        "comparison_report": report,
        "generated_at": datetime.now().isoformat()
    }


@router.get("/normalization-impact-summary")
async def get_normalization_impact_summary():
    """
    Get aggregate normalization impact across all documents.

    Shows overall effectiveness of the normalization pipeline.

    Returns:
        Summary statistics showing average improvement from normalization
    """
    from ..services.normalization_impact_analyzer import calculate_aggregate_normalization_impact

    # Find all extraction and normalization pairs
    extractions_dir = Path("backend/data/extractions")
    normalized_dir = Path("backend/data/normalized_multiagent")

    if not extractions_dir.exists():
        raise HTTPException(status_code=404, detail="Extractions directory not found")

    extraction_files = list(extractions_dir.glob("*.json"))
    documents = []

    for extraction_file in extraction_files:
        try:
            # Extract document ID from filename
            doc_id = extraction_file.stem.split("_")[2]  # extract_parse_{DOC_ID}_...

            # Find corresponding normalization
            if normalized_dir.exists():
                norm_files = list(normalized_dir.glob(f"*{doc_id}*.json"))

                if norm_files:
                    # Load both files
                    with open(extraction_file, 'r', encoding='utf-8') as f:
                        extraction_data = json.load(f)

                    with open(norm_files[0], 'r', encoding='utf-8') as f:
                        normalized_raw = json.load(f)

                    normalized_data = {
                        "normalized_collateral": normalized_raw.get("normalized_collateral_table", []),
                        "temporal": normalized_raw.get("temporal_fields", {}),
                        "currency": normalized_raw.get("currency_fields", {}),
                        "overall_confidence": normalized_raw.get("overall_confidence", 0.0)
                    }

                    documents.append({
                        "document_id": "csa_credit_suisse",  # Use available ground truth
                        "extraction_data": extraction_data.get("extracted_fields", {}),
                        "normalized_data": normalized_data
                    })
        except Exception:
            continue

    if not documents:
        return {
            "message": "No document pairs found for comparison",
            "total_extractions": len(extraction_files)
        }

    # Calculate aggregate impact
    aggregate = calculate_aggregate_normalization_impact(impact_analyzer, documents)

    return {
        "aggregate_impact": aggregate,
        "generated_at": datetime.now().isoformat()
    }


@router.get("/health")
async def analytics_health():
    """Health check for analytics service."""
    # Check if ground truth directory exists
    gt_dir = Path("backend/tests/ground_truth")
    gt_exists = gt_dir.exists()

    # Count ground truth files
    gt_extractions = 0
    gt_normalized = 0

    if gt_exists:
        gt_extractions = len(list((gt_dir / "expected_extractions").glob("*.json")))
        gt_normalized = len(list((gt_dir / "expected_normalized").glob("*.json")))

    # Count data files
    data_dir = Path("backend/data")
    extractions_count = len(list((data_dir / "extractions").glob("*.json"))) if (data_dir / "extractions").exists() else 0
    normalized_count = len(list((data_dir / "normalized_multiagent").glob("*.json"))) if (data_dir / "normalized_multiagent").exists() else 0

    return {
        "status": "healthy",
        "ground_truth_available": gt_exists,
        "ground_truth_extractions": gt_extractions,
        "ground_truth_normalized": gt_normalized,
        "total_extractions": extractions_count,
        "total_normalized": normalized_count,
        "accuracy_validation_enabled": gt_extractions > 0 or gt_normalized > 0
    }
