"""API endpoints for collateral CSV import and matching."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.config import settings
from app.models.schemas import ParsedCollateralItem, MatchedCollateralItem, CSATerms
from app.services.collateral_parser import parse_collateral_csv, validate_parsed_items
from app.services.collateral_matcher import CollateralMatcherService
from app.utils.file_storage import FileStorage

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class ImportCollateralResponse(BaseModel):
    """Response after importing and parsing CSV."""
    document_id: str
    parsed_items: List[ParsedCollateralItem]
    total_rows: int
    valid_rows: int
    error_rows: int
    errors: List[str] = Field(default_factory=list)


class MatchCollateralRequest(BaseModel):
    """Request to match parsed collateral to CSA terms."""
    document_id: str
    parsed_items: List[ParsedCollateralItem]
    default_scenario: Optional[str] = None


class MatchCollateralResponse(BaseModel):
    """Response after matching collateral."""
    document_id: str
    matched_items: List[MatchedCollateralItem]
    summary: dict


class HaircutLookupRequest(BaseModel):
    """Request to lookup haircut for specific collateral."""
    document_id: str
    csa_description: str
    rating_event: str
    maturity_min: Optional[float] = None
    maturity_max: Optional[float] = None


class HaircutLookupResponse(BaseModel):
    """Response with haircut information."""
    haircut: Optional[float]
    bucket_min: Optional[float]
    bucket_max: Optional[float]
    warnings: List[str]


@router.post("/import", response_model=ImportCollateralResponse)
async def import_collateral_csv(
    file: UploadFile = File(...),
    document_id: str = Form(...)
):
    """
    Import and parse collateral CSV file.

    This endpoint:
    1. Validates the CSV format and headers
    2. Parses each row into ParsedCollateralItem
    3. Validates required fields and data types
    4. Returns parsed items with any validation errors

    Expected CSV columns:
    - description (required)
    - market_value (required)
    - maturity_min (optional)
    - maturity_max (optional)
    - currency (optional, default USD)
    - valuation_scenario (optional)
    """
    try:
        logger.info(f"Importing collateral CSV for document {document_id}")

        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="File must be a CSV file"
            )

        # Read file content
        file_content = await file.read()

        # Parse CSV
        parsed_items = parse_collateral_csv(file_content, document_id)

        # Validate parsed items
        is_valid, error_messages = validate_parsed_items(parsed_items)

        # Count valid vs error rows
        error_rows = sum(1 for item in parsed_items if item.parse_errors)
        valid_rows = len(parsed_items) - error_rows

        logger.info(f"Parsed {len(parsed_items)} rows: {valid_rows} valid, {error_rows} errors")

        return ImportCollateralResponse(
            document_id=document_id,
            parsed_items=parsed_items,
            total_rows=len(parsed_items),
            valid_rows=valid_rows,
            error_rows=error_rows,
            errors=error_messages
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing CSV: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import CSV: {str(e)}"
        )


@router.post("/match", response_model=MatchCollateralResponse)
async def match_collateral(request: MatchCollateralRequest):
    """
    Match parsed collateral items to CSA collateral descriptions using AI.

    This endpoint:
    1. Loads CSA terms for the document
    2. Uses LLM to match CSV descriptions to CSA collateral descriptions
    3. Matches maturity ranges to CSA maturity buckets
    4. Looks up haircuts for each matched item
    5. Returns matched items with confidence scores and warnings

    The matching considers both collateral description AND maturity range.
    """
    try:
        logger.info(f"Matching {len(request.parsed_items)} collateral items for document {request.document_id}")

        # Load CSA terms
        csa_terms = FileStorage.load_csa_terms(
            request.document_id,
            settings.csa_terms_dir
        )

        if not csa_terms:
            raise HTTPException(
                status_code=404,
                detail=f"CSA terms not found for document {request.document_id}"
            )

        # Set default scenario if not specified per item
        default_scenario = request.default_scenario
        if not default_scenario and csa_terms.eligible_collateral:
            # Use first rating event from first collateral as default
            first_collateral = csa_terms.eligible_collateral[0]
            rating_events = getattr(first_collateral, 'rating_events', [])
            default_scenario = rating_events[0] if rating_events else "No Rating Event"

        for item in request.parsed_items:
            if not item.valuation_scenario:
                item.valuation_scenario = default_scenario

        # Initialize matcher service
        matcher_service = CollateralMatcherService()

        # AI match descriptions
        matched_items = matcher_service.match_collateral_to_csa(
            request.parsed_items,
            csa_terms
        )

        # Lookup haircuts for matched items
        for item in matched_items:
            if item.matched_csa_description:
                haircut, bucket_min, bucket_max, warnings = csa_terms.get_haircut_for_collateral_range(
                    item.matched_csa_description,
                    item.valuation_scenario,
                    item.maturity_min,
                    item.maturity_max
                )

                item.haircut_rate = haircut or 0.0
                item.matched_maturity_bucket_min = bucket_min
                item.matched_maturity_bucket_max = bucket_max
                item.haircut_source = "auto" if haircut else "default_zero"
                item.warnings.extend(warnings)

                if not haircut:
                    item.warnings.append(
                        "No haircut found - defaulting to 0%. Please verify manually."
                    )

        # Build summary
        summary = {
            "total_items": len(matched_items),
            "high_confidence": sum(1 for m in matched_items if m.match_confidence >= 0.8),
            "medium_confidence": sum(1 for m in matched_items if 0.5 <= m.match_confidence < 0.8),
            "low_confidence": sum(1 for m in matched_items if m.match_confidence < 0.5),
            "warnings_count": sum(len(m.warnings) for m in matched_items),
            "total_market_value": sum(m.market_value for m in matched_items),
            "total_effective_value": sum(m.effective_value for m in matched_items)
        }

        logger.info(f"Matched {len(matched_items)} items: {summary['high_confidence']} high confidence")

        return MatchCollateralResponse(
            document_id=request.document_id,
            matched_items=matched_items,
            summary=summary
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error matching collateral: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to match collateral: {str(e)}"
        )


@router.post("/lookup-haircut", response_model=HaircutLookupResponse)
async def lookup_haircut(request: HaircutLookupRequest):
    """
    Lookup haircut for specific collateral type and maturity range.

    This endpoint is used by the frontend when users manually change:
    - Matched collateral type
    - Valuation scenario
    - Maturity range

    It returns the appropriate haircut and matched maturity bucket.
    """
    try:
        logger.info(f"Looking up haircut for {request.csa_description} under {request.rating_event}")

        # Load CSA terms
        csa_terms = FileStorage.load_csa_terms(
            request.document_id,
            settings.csa_terms_dir
        )

        if not csa_terms:
            raise HTTPException(
                status_code=404,
                detail=f"CSA terms not found for document {request.document_id}"
            )

        # Lookup haircut
        haircut, bucket_min, bucket_max, warnings = csa_terms.get_haircut_for_collateral_range(
            request.csa_description,
            request.rating_event,
            request.maturity_min,
            request.maturity_max
        )

        return HaircutLookupResponse(
            haircut=haircut,
            bucket_min=bucket_min,
            bucket_max=bucket_max,
            warnings=warnings
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error looking up haircut: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to lookup haircut: {str(e)}"
        )
