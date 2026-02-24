"""
API endpoints for CSA formula pattern analysis.

Provides endpoints to extract and retrieve formula patterns from CSA documents.
These patterns describe the calculation logic used in the CSA (e.g., greatest_of,
rating-dependent thresholds, etc.)
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.services.pattern_extraction_service import PatternExtractionService
from app.models.formula_schemas import FormulaPatternResult
from app.models.schemas import CSATerms
from app.utils.file_storage import FileStorage

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class ExtractPatternsRequest(BaseModel):
    """Request to extract formula patterns from a CSA document."""

    document_id: str = Field(description="CSA document ID")
    force_reextract: bool = Field(
        default=False,
        description="Force re-extraction even if patterns already exist"
    )


class ExtractPatternsResponse(BaseModel):
    """Response after extracting formula patterns."""

    status: str = Field(description="Status of the extraction")
    document_id: str = Field(description="Document ID")
    patterns: FormulaPatternResult = Field(description="Extracted pattern results")
    extraction_time_seconds: float = Field(description="Time taken for extraction")
    cached: bool = Field(
        default=False,
        description="Whether result was loaded from cache"
    )


class GetPatternsResponse(BaseModel):
    """Response for retrieving stored patterns."""

    patterns: FormulaPatternResult
    cached: bool = True


@router.post("/{document_id}/extract-patterns", response_model=ExtractPatternsResponse)
async def extract_formula_patterns(
    document_id: str,
    force_reextract: bool = Query(
        default=False,
        description="Force re-extraction even if patterns already exist"
    )
):
    """
    Extract formula patterns from a CSA document.

    This endpoint triggers the Clause Agent to analyze the document
    and extract calculation formula patterns including:
    - Delivery/Return Amount patterns (greatest_of, sum_of, etc.)
    - Threshold structures (fixed, variable_by_rating, etc.)
    - Collateral haircut dependencies (fixed, rating_dependent, matrix)
    - MTA, rounding, and independent amount rules

    The result is saved for later retrieval and can be used to enhance
    margin calculation explanations.

    Args:
        document_id: CSA document identifier
        force_reextract: If True, re-extract even if patterns already exist

    Returns:
        ExtractPatternsResponse with extracted patterns and metadata

    Raises:
        HTTPException 404: If document not found or CSA terms not available
        HTTPException 500: If pattern extraction fails
    """
    try:
        # Use the pattern extraction service
        service = PatternExtractionService(settings.anthropic_api_key)

        patterns, cached, elapsed = await service.extract_or_load_patterns(
            document_id=document_id,
            force_reextract=force_reextract
        )

        return ExtractPatternsResponse(
            status="success",
            document_id=document_id,
            patterns=patterns,
            extraction_time_seconds=elapsed,
            cached=cached
        )

    except FileNotFoundError as e:
        # Convert FileNotFoundError to HTTPException with 404
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        logger.error(f"Pattern extraction failed for {document_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Pattern extraction failed: {str(e)}"
        )


@router.get("/{document_id}/patterns", response_model=GetPatternsResponse)
async def get_formula_patterns(document_id: str):
    """
    Retrieve previously extracted formula patterns for a document.

    Args:
        document_id: CSA document identifier

    Returns:
        GetPatternsResponse with stored patterns

    Raises:
        HTTPException 404: If patterns not found for this document
    """
    try:
        # Load patterns
        patterns_data = FileStorage.load_json(
            settings.formula_patterns_dir,
            f"patterns_{document_id}"
        )

        if not patterns_data:
            raise HTTPException(
                status_code=404,
                detail=f"Formula patterns not found for document {document_id}. "
                       f"Run pattern extraction first."
            )

        patterns = FormulaPatternResult(**patterns_data)

        logger.info(f"Retrieved formula patterns for document {document_id}")

        return GetPatternsResponse(
            patterns=patterns,
            cached=True
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error retrieving patterns for {document_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving patterns: {str(e)}"
        )


@router.delete("/{document_id}/patterns")
async def delete_formula_patterns(document_id: str):
    """
    Delete stored formula patterns for a document.

    Useful for forcing re-extraction or cleanup.

    Args:
        document_id: CSA document identifier

    Returns:
        Status message

    Raises:
        HTTPException 404: If patterns not found
    """
    import os

    try:
        patterns_path = os.path.join(
            settings.formula_patterns_dir,
            f"patterns_{document_id}.json"
        )

        if not os.path.exists(patterns_path):
            raise HTTPException(
                status_code=404,
                detail=f"Formula patterns not found for document {document_id}"
            )

        os.remove(patterns_path)
        logger.info(f"Deleted formula patterns for document {document_id}")

        return {
            "status": "success",
            "message": f"Formula patterns deleted for document {document_id}",
            "document_id": document_id
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error deleting patterns for {document_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting patterns: {str(e)}"
        )


@router.get("/{document_id}/complexity-analysis")
async def get_complexity_analysis(document_id: str):
    """
    Get detailed complexity analysis for a CSA document.

    Returns breakdown of complexity factors and assessment.

    Args:
        document_id: CSA document identifier

    Returns:
        Complexity analysis with factor breakdown

    Raises:
        HTTPException 404: If patterns not found
    """
    try:
        # Load patterns
        patterns_data = FileStorage.load_json(
            settings.formula_patterns_dir,
            f"patterns_{document_id}"
        )

        if not patterns_data:
            raise HTTPException(
                status_code=404,
                detail=f"Formula patterns not found for document {document_id}. "
                       f"Run pattern extraction first."
            )

        patterns = FormulaPatternResult(**patterns_data)

        # Get complexity factors
        complexity_factors = patterns.assess_complexity_factors()

        # Add CSA type label
        csa_type = patterns.get_csa_type_label()

        return {
            "document_id": document_id,
            "csa_type": csa_type,
            "complexity_score": patterns.complexity_score,
            "complexity_factors": complexity_factors,
            "pattern_summary": {
                "delivery_amount_type": patterns.patterns.get("delivery_amount", {}).pattern_type if "delivery_amount" in patterns.patterns else "unknown",
                "threshold_structure": patterns.threshold_structure.structure_type,
                "haircut_dependency": patterns.haircut_structure.dependency_type
            },
            "variations_detected": patterns.variations_summary,
            "confidence": patterns.overall_confidence
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error getting complexity analysis for {document_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing complexity: {str(e)}"
        )
