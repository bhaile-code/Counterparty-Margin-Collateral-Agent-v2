"""Export endpoints for margin call notices and audit trails."""

import csv
import io
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from app.config import settings
from app.models.schemas import (
    AuditTrailEvent,
    CalculationBreakdownStep,
    MarginCallAction,
    MarginCallNotice,
)
from app.utils.file_storage import FileStorage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["exports"])


@router.get("/margin-call-notice/{calculation_id}")
async def export_margin_call_notice(
    calculation_id: str,
    format: Literal["json", "pdf"] = Query(
        "json", description="Export format: json or pdf"
    ),
):
    """
    Export a margin call notice in JSON or PDF format.

    The notice includes:
    - Counterparty information
    - Exposure and collateral summary
    - Margin call amount and action required
    - Calculation breakdown
    - Delivery deadlines
    - Legal disclaimer

    Args:
        calculation_id: The ID of the calculation to export
        format: Export format (json or pdf)

    Returns:
        JSON response or PDF file download
    """
    try:
        # Load calculation result
        margin_call = FileStorage.load_margin_call(
            calculation_id, settings.calculations_dir
        )
        if not margin_call:
            raise HTTPException(
                status_code=404,
                detail=f"Calculation {calculation_id} not found. Please run POST /api/v1/calculations/calculate first.",
            )

        # Load CSA terms
        # Handle both dict and Pydantic model
        if hasattr(margin_call, 'model_dump'):
            margin_call_dict = margin_call.model_dump()
            document_id = margin_call_dict.get("csa_terms_id") or margin_call_dict.get("document_id")
        else:
            document_id = margin_call.get("csa_terms_id") or margin_call.get("document_id")

        if not document_id:
            raise HTTPException(
                status_code=400,
                detail="Calculation missing document_id reference. Cannot load CSA terms.",
            )

        csa_terms = FileStorage.load_csa_terms(document_id, settings.csa_terms_dir)
        if not csa_terms:
            raise HTTPException(
                status_code=404,
                detail=f"CSA terms not found for document {document_id}. Cannot generate margin call notice.",
            )

        # Try to load explanation for additional details
        explanation = FileStorage.load_explanation(
            calculation_id, settings.explanations_dir
        )

        # Build margin call notice
        notice = _build_margin_call_notice(
            calculation_id, document_id, margin_call, csa_terms, explanation
        )

        if format == "json":
            return notice
        elif format == "pdf":
            # Import here to avoid loading reportlab unless needed
            from app.utils.pdf_generator import generate_margin_call_notice_pdf

            pdf_bytes = generate_margin_call_notice_pdf(notice)

            # Return PDF as downloadable file
            filename = f"margin_call_notice_{calculation_id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error exporting margin call notice for calculation {calculation_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export margin call notice: {str(e)}",
        )


@router.get("/audit-trail/{calculation_id}")
async def export_audit_trail(
    calculation_id: str,
    format: Literal["json", "csv"] = Query(
        "json", description="Export format: json or csv"
    ),
):
    """
    Export the audit trail for a calculation in JSON or CSV format.

    The audit trail includes:
    - Chronological event log
    - Timestamps for each event
    - Event descriptions and details
    - Complete calculation history

    Args:
        calculation_id: The ID of the calculation
        format: Export format (json or csv)

    Returns:
        JSON response or CSV file download
    """
    try:
        # Load explanation (which contains audit trail)
        explanation = FileStorage.load_explanation(
            calculation_id, settings.explanations_dir
        )
        if not explanation:
            raise HTTPException(
                status_code=404,
                detail=f"Explanation not found for calculation {calculation_id}. Run POST /api/v1/calculations/{calculation_id}/explain first.",
            )

        audit_trail = explanation.get("audit_trail", [])
        if not audit_trail:
            raise HTTPException(
                status_code=404,
                detail=f"No audit trail found in explanation for calculation {calculation_id}.",
            )

        # Convert to AuditTrailEvent models
        audit_events = [AuditTrailEvent(**event) for event in audit_trail]

        if format == "json":
            return {
                "calculation_id": calculation_id,
                "generated_at": datetime.utcnow().isoformat(),
                "event_count": len(audit_events),
                "audit_trail": [event.model_dump() for event in audit_events],
            }
        elif format == "csv":
            # Generate CSV
            output = io.StringIO()
            writer = csv.DictWriter(
                output, fieldnames=["timestamp", "event", "details"]
            )
            writer.writeheader()
            for event in audit_events:
                writer.writerow(event.model_dump())

            # Return CSV as downloadable file
            filename = f"audit_trail_{calculation_id}_{datetime.utcnow().strftime('%Y%m%d')}.csv"
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode("utf-8")),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error exporting audit trail for calculation {calculation_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to export audit trail: {str(e)}"
        )


def _build_margin_call_notice(
    calculation_id: str,
    document_id: str,
    margin_call,  # Can be dict or MarginCall model
    csa_terms,  # Can be dict or CSATerms model
    explanation: dict = None,
) -> MarginCallNotice:
    """
    Build a structured margin call notice from calculation data.

    Args:
        calculation_id: Calculation ID
        document_id: Document ID
        margin_call: Margin call calculation result (dict or MarginCall model)
        csa_terms: CSA terms (dict or CSATerms model)
        explanation: Optional explanation with breakdown

    Returns:
        MarginCallNotice model
    """
    # Convert to dict if needed
    if hasattr(margin_call, 'model_dump'):
        margin_call = margin_call.model_dump()
    if hasattr(csa_terms, 'model_dump'):
        csa_terms = csa_terms.model_dump()

    # Extract calculation breakdown from explanation if available
    calculation_breakdown = []
    if explanation and "calculation_breakdown" in explanation:
        calculation_breakdown = [
            CalculationBreakdownStep(**step)
            for step in explanation["calculation_breakdown"]
        ]

    # Determine party names
    party_a = csa_terms.get("party_a", "Your Firm")
    party_b = margin_call.get("counterparty_name") or csa_terms.get("party_b", "Counterparty")

    # Build eligible collateral summary
    eligible_collateral = csa_terms.get("eligible_collateral", [])
    if eligible_collateral:
        collateral_types = set()
        for item in eligible_collateral:
            if isinstance(item, dict):
                collateral_type = item.get("standardized_type", "UNKNOWN")
                collateral_types.add(collateral_type)
        eligible_collateral_summary = (
            f"Acceptable collateral types: {', '.join(sorted(collateral_types))}"
        )
    else:
        eligible_collateral_summary = "Refer to CSA for eligible collateral types."

    # Handle infinity values for export (convert to very large number for display)
    threshold_value = csa_terms.get("party_a_threshold")
    if threshold_value is None or math.isinf(threshold_value):
        threshold_value = 999_999_999_999.0  # Represent infinity as very large number

    independent_amount_value = csa_terms.get("party_a_independent_amount")
    if independent_amount_value is None:
        independent_amount_value = 0.0
    elif math.isinf(independent_amount_value):
        independent_amount_value = 999_999_999_999.0

    # Build notice
    notice = MarginCallNotice(
        calculation_id=calculation_id,
        document_id=document_id,
        party_a=party_a,
        party_b=party_b,
        current_exposure=margin_call.get("net_exposure", 0),
        threshold=threshold_value,
        posted_collateral_value=margin_call.get("effective_collateral", 0),
        independent_amount=independent_amount_value,
        margin_call_action=MarginCallAction(margin_call.get("action", "NO_ACTION")),
        margin_call_amount=margin_call.get("amount", 0),
        delivery_amount=margin_call.get("amount", 0),
        valuation_date=datetime.utcnow().strftime("%Y-%m-%d"),
        calculation_breakdown=calculation_breakdown,
        eligible_collateral_summary=eligible_collateral_summary,
    )

    return notice
