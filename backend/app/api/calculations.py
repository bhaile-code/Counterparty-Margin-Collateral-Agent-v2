"""API endpoints for margin calculations and explanations."""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.core.calculator import calculate_margin_requirement
from app.models.schemas import (
    CollateralItem,
    MarginCall,
    CSATerms,
    ExplanationResponse,
    MarginCallExplanation,
    Currency,
)
from app.models.formula_schemas import FormulaPatternResult
from app.services.llm_service import explanation_generator_service
from app.utils.file_storage import FileStorage
from app.utils.constants import is_infinite_threshold

logger = logging.getLogger(__name__)

router = APIRouter()


# Request models for API
class CalculateMarginRequest(BaseModel):
    """Request to calculate margin requirement."""

    document_id: str = Field(description="CSA document ID")
    net_exposure: float = Field(description="Net exposure amount")
    posted_collateral: List[CollateralItem] = Field(
        default_factory=list, description="List of posted collateral items"
    )
    party_perspective: str = Field(
        default="party_b",
        description="Which party's perspective to calculate from: 'party_a' or 'party_b'"
    )


class CalculationResponse(BaseModel):
    """Response after calculating margin."""

    calculation_id: str
    document_id: str
    margin_call: MarginCall
    status: str = "calculated"
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    has_explanation: bool = False
    has_formula_pattern: bool = False


class CalculationSummary(BaseModel):
    """Summary of a calculation for list views."""

    calculation_id: str
    calculation_date: datetime
    net_exposure: float
    party_perspective: str = Field(description="party_a or party_b")
    action: str = Field(description="CALL, RETURN, or NO_ACTION")
    amount: float
    currency: str
    counterparty_name: Optional[str] = None
    has_explanation: bool = False
    has_formula_pattern: bool = False


@router.post("/calculate", response_model=CalculationResponse)
async def calculate_margin(request: CalculateMarginRequest):
    """
    Calculate margin requirement based on CSA terms.

    This endpoint:
    1. Loads CSA terms for the specified document
    2. Runs the margin calculation
    3. Saves the calculation result
    4. Returns the margin call details

    Note: This is a simplified implementation for Phase 5 testing.
    Full implementation will be in Phase 6.
    """
    try:
        # Load CSA terms
        csa_terms = FileStorage.load_csa_terms(
            request.document_id, settings.csa_terms_dir
        )

        if not csa_terms:
            raise HTTPException(
                status_code=404,
                detail=f"CSA terms not found for document {request.document_id}. "
                f"Please run the document mapping workflow first.",
            )

        # Validate party_perspective parameter
        if request.party_perspective not in ["party_a", "party_b"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid party_perspective: '{request.party_perspective}'. Must be 'party_a' or 'party_b'."
            )

        # Select party-specific values based on perspective
        if request.party_perspective == "party_a":
            threshold = csa_terms.party_a_threshold
            minimum_transfer_amount = csa_terms.party_a_minimum_transfer_amount
            independent_amount = csa_terms.party_a_independent_amount
        else:  # party_b
            threshold = csa_terms.party_b_threshold
            minimum_transfer_amount = csa_terms.party_b_minimum_transfer_amount
            independent_amount = csa_terms.party_b_independent_amount

        # Validate that values are available
        # Note: threshold can be infinity (which is valid), but not None
        if threshold is None:
            raise HTTPException(
                status_code=400,
                detail=f"Missing {request.party_perspective} threshold in CSA document. "
                f"Please ensure the document has been properly extracted."
            )

        if minimum_transfer_amount is None:
            raise HTTPException(
                status_code=400,
                detail=f"Missing {request.party_perspective} minimum transfer amount in CSA document. "
                f"Please ensure the document has been properly extracted."
            )

        # Format threshold for logging
        threshold_str = "∞" if is_infinite_threshold(threshold) else f"${threshold:,.2f}"

        logger.info(
            f"Calculating margin for {csa_terms.party_a or 'Unknown'} vs {csa_terms.party_b or 'Unknown'}, "
            f"Perspective: {request.party_perspective}, "
            f"Threshold: {threshold_str}, "
            f"Exposure: ${request.net_exposure:,.2f}"
        )

        # Run calculation with party-specific values
        margin_call = calculate_margin_requirement(
            net_exposure=request.net_exposure,
            threshold=threshold,
            minimum_transfer_amount=minimum_transfer_amount,
            rounding=csa_terms.rounding,
            posted_collateral=request.posted_collateral,
            independent_amount=independent_amount or 0.0,
        )

        # Add references to the margin call
        margin_call.csa_terms_id = request.document_id

        # Derive counterparty name from perspective
        # If we're party_a, the counterparty is party_b, and vice versa
        if request.party_perspective == "party_a":
            margin_call.counterparty_name = csa_terms.party_b
        else:  # party_b perspective (default)
            margin_call.counterparty_name = csa_terms.party_a

        # Generate calculation ID
        calculation_id = FileStorage.generate_id("calc", request.document_id)

        # Save calculation result
        FileStorage.save_margin_call(
            margin_call, settings.calculations_dir, calculation_id
        )

        logger.info(
            f"Calculation complete: {margin_call.action.value} "
            f"${margin_call.amount:,.2f}"
        )

        return CalculationResponse(
            calculation_id=calculation_id,
            document_id=request.document_id,
            margin_call=margin_call,
            status="calculated",
            calculated_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating margin: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")


@router.post("/{calculation_id}/explain", response_model=ExplanationResponse)
async def generate_explanation(calculation_id: str):
    """
    Generate LLM-powered explanation for a margin calculation.

    This endpoint:
    1. Loads the calculation result
    2. Loads the CSA terms
    3. Generates a comprehensive explanation with citations
    4. Saves the explanation
    5. Returns the explanation

    The explanation includes:
    - Narrative summary with CSA clause citations
    - Step-by-step calculation breakdown
    - Key factors that influenced the result
    - Audit trail
    - Risk assessment
    - Recommended next steps
    """
    try:
        logger.info(f"Generating explanation for calculation {calculation_id}")

        # Load calculation result
        margin_call = FileStorage.load_margin_call(
            calculation_id, settings.calculations_dir
        )

        if not margin_call:
            raise HTTPException(
                status_code=404, detail=f"Calculation {calculation_id} not found"
            )

        # Extract document_id from calculation_id
        # Format: calc_{document_id}_{timestamp}
        parts = calculation_id.split("_")
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Invalid calculation ID format")

        # Reconstruct document_id (everything between 'calc_' and the timestamp)
        document_id = margin_call.csa_terms_id or "_".join(parts[1:-2])

        # Load CSA terms
        csa_terms = FileStorage.load_csa_terms(document_id, settings.csa_terms_dir)

        if not csa_terms:
            raise HTTPException(
                status_code=404,
                detail=f"CSA terms not found for document {document_id}",
            )

        logger.info(
            f"Loaded calculation and CSA terms for {margin_call.counterparty_name or 'Unknown'}"
        )

        # Try to load formula patterns if available (enhances explanation quality)
        formula_patterns = None
        try:
            patterns_data = FileStorage.load_json(
                settings.formula_patterns_dir,
                f"patterns_{document_id}"
            )
            if patterns_data:
                formula_patterns = FormulaPatternResult(**patterns_data)
                logger.info(
                    f"Loaded formula patterns for {document_id}: "
                    f"CSA type={formula_patterns.get_csa_type_label()}, "
                    f"complexity={formula_patterns.complexity_score:.2f}"
                )
            else:
                logger.info(
                    f"No formula patterns found for {document_id} - "
                    f"generating standard explanation"
                )
        except Exception as e:
            logger.warning(
                f"Could not load formula patterns for {document_id}: {str(e)}. "
                f"Generating explanation without pattern context."
            )
            # Continue without patterns - this is not a fatal error

        # Generate explanation using LLM service (with optional pattern context)
        explanation_data = explanation_generator_service.generate_explanation(
            margin_call=margin_call,
            csa_terms=csa_terms,
            document_id=document_id,
            formula_patterns=formula_patterns
        )

        # Save explanation
        FileStorage.save_explanation(
            explanation_data, settings.explanations_dir, calculation_id
        )

        logger.info(f"Successfully generated explanation for {calculation_id}")

        # Convert to Pydantic model for response validation
        explanation = MarginCallExplanation(**explanation_data)

        return ExplanationResponse(
            status="success",
            explanation=explanation,
            message=f"Explanation generated for {margin_call.counterparty_name or 'Unknown'}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error generating explanation for {calculation_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Explanation generation failed: {str(e)}"
        )


@router.get("/{calculation_id}", response_model=CalculationResponse)
async def get_calculation(calculation_id: str):
    """
    Retrieve a previously calculated margin result.

    Returns the full calculation details including all steps.
    """
    try:
        # Load calculation result
        margin_call = FileStorage.load_margin_call(
            calculation_id, settings.calculations_dir
        )

        if not margin_call:
            raise HTTPException(
                status_code=404, detail=f"Calculation {calculation_id} not found"
            )

        # Extract document_id from margin_call
        document_id = margin_call.csa_terms_id or "unknown"

        # Check if explanation and formula pattern exist
        has_explanation = FileStorage.explanation_exists(
            calculation_id, settings.explanations_dir
        )
        has_formula_pattern = FileStorage.formula_pattern_exists(
            document_id, settings.formula_patterns_dir
        )

        return CalculationResponse(
            calculation_id=calculation_id,
            document_id=document_id,
            margin_call=margin_call,
            status="retrieved",
            calculated_at=margin_call.calculation_date,
            has_explanation=has_explanation,
            has_formula_pattern=has_formula_pattern,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving calculation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve calculation: {str(e)}"
        )


@router.get("/{calculation_id}/explanation")
async def get_explanation(calculation_id: str):
    """
    Retrieve a previously generated explanation.

    Returns the full explanation with all citations and breakdowns.
    """
    try:
        # Load explanation
        explanation_data = FileStorage.load_explanation(
            calculation_id, settings.explanations_dir
        )

        if not explanation_data:
            raise HTTPException(
                status_code=404,
                detail=f"Explanation not found for calculation {calculation_id}. "
                f"Generate it first using POST /{calculation_id}/explain",
            )

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "calculation_id": calculation_id,
                "explanation": explanation_data,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving explanation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve explanation: {str(e)}"
        )


@router.get("/")
async def list_calculations():
    """
    List all calculations.

    Returns a list of all calculation IDs.
    """
    try:
        calculation_ids = FileStorage.list_files(settings.calculations_dir)

        # Remove 'margin_call_' prefix from filenames
        calculation_ids = [cid.replace("margin_call_", "") for cid in calculation_ids]

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "count": len(calculation_ids),
                "calculation_ids": calculation_ids,
            },
        )

    except Exception as e:
        logger.error(f"Error listing calculations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list calculations: {str(e)}"
        )


@router.get("/by-document/{document_id}")
async def list_calculations_by_document(document_id: str):
    """
    List all calculations for a specific document.

    Returns a list of calculation summaries sorted by date (newest first).
    """
    try:
        # Get calculation IDs for this document
        calculation_ids = FileStorage.list_calculations_by_document(
            document_id, settings.calculations_dir
        )

        # Load CSA terms to determine party perspective for each calculation
        csa_terms = FileStorage.load_csa_terms(document_id, settings.csa_terms_dir)

        # Load each calculation and build summaries
        summaries = []
        for calc_id in calculation_ids:
            try:
                margin_call = FileStorage.load_margin_call(
                    calc_id, settings.calculations_dir
                )
                if not margin_call:
                    continue

                # Determine party perspective from counterparty name
                party_perspective = "party_b"  # default
                if csa_terms and margin_call.counterparty_name:
                    if margin_call.counterparty_name == csa_terms.party_a:
                        party_perspective = "party_b"
                    elif margin_call.counterparty_name == csa_terms.party_b:
                        party_perspective = "party_a"

                # Check if explanation and formula pattern exist
                has_explanation = FileStorage.explanation_exists(
                    calc_id, settings.explanations_dir
                )
                has_formula_pattern = FileStorage.formula_pattern_exists(
                    document_id, settings.formula_patterns_dir
                )

                summary = CalculationSummary(
                    calculation_id=calc_id,
                    calculation_date=margin_call.calculation_date,
                    net_exposure=margin_call.net_exposure,
                    party_perspective=party_perspective,
                    action=margin_call.action.value,
                    amount=margin_call.amount,
                    currency=margin_call.currency.value,
                    counterparty_name=margin_call.counterparty_name,
                    has_explanation=has_explanation,
                    has_formula_pattern=has_formula_pattern,
                )
                summaries.append(summary)

            except Exception as e:
                logger.warning(f"Error loading calculation {calc_id}: {str(e)}")
                continue

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "document_id": document_id,
                "count": len(summaries),
                "calculations": [s.model_dump(mode='json') for s in summaries],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error listing calculations for document {document_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list calculations for document: {str(e)}",
        )
