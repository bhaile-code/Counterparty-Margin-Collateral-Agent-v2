"""PDF generation utility for margin call notices."""

import io
from datetime import datetime
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from app.models.schemas import MarginCallNotice


def generate_margin_call_notice_pdf(notice: MarginCallNotice) -> bytes:
    """
    Generate a PDF margin call notice from structured data.

    Args:
        notice: MarginCallNotice model with all required data

    Returns:
        PDF file as bytes
    """
    # Create PDF buffer
    buffer = io.BytesIO()

    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    # Container for PDF elements
    elements = []

    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#333333"),
        spaceAfter=12,
        spaceBefore=12,
    )
    normal_style = styles["Normal"]
    small_style = ParagraphStyle(
        "Small", parent=styles["Normal"], fontSize=9, textColor=colors.grey
    )

    # Title
    elements.append(Paragraph("MARGIN CALL NOTICE", title_style))
    elements.append(Spacer(1, 0.1 * inch))

    # Document metadata
    metadata_data = [
        ["Calculation ID:", notice.calculation_id],
        ["Generated:", notice.generated_at.strftime("%Y-%m-%d %H:%M UTC")],
        ["Valuation Date:", notice.valuation_date],
    ]
    metadata_table = Table(metadata_data, colWidths=[1.5 * inch, 4 * inch])
    metadata_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
            ]
        )
    )
    elements.append(metadata_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Counterparty Section
    elements.append(Paragraph("PARTIES", heading_style))
    parties_data = [
        ["Party A:", notice.party_a],
        ["Party B:", notice.party_b],
    ]
    parties_table = Table(parties_data, colWidths=[1.5 * inch, 5 * inch])
    parties_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(parties_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Executive Summary
    elements.append(Paragraph("MARGIN CALL SUMMARY", heading_style))
    action_color = (
        colors.red
        if notice.margin_call_action.value == "CALL"
        else colors.green
        if notice.margin_call_action.value == "RETURN"
        else colors.grey
    )

    summary_data = [
        ["Current Exposure:", f"${notice.current_exposure:,.2f}"],
        ["Collateral Threshold:", f"${notice.threshold:,.2f}"],
        ["Posted Collateral (after haircuts):", f"${notice.posted_collateral_value:,.2f}"],
        ["Independent Amount:", f"${notice.independent_amount:,.2f}"],
        ["", ""],
        ["MARGIN CALL ACTION:", notice.margin_call_action.value],
        ["MARGIN CALL AMOUNT:", f"${notice.margin_call_amount:,.2f}"],
        ["DELIVERY AMOUNT (rounded):", f"${notice.delivery_amount:,.2f}"],
    ]

    summary_table = Table(summary_data, colWidths=[3 * inch, 3 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                # Highlight action row
                ("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#f0f0f0")),
                ("FONTSIZE", (0, 5), (-1, 7), 12),
                ("FONTNAME", (0, 5), (-1, 7), "Helvetica-Bold"),
                ("TEXTCOLOR", (1, 5), (1, 5), action_color),
                # Grid
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("LINEABOVE", (0, 5), (-1, 5), 2, colors.black),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Calculation Breakdown
    if notice.calculation_breakdown:
        elements.append(Paragraph("CALCULATION BREAKDOWN", heading_style))
        for step in notice.calculation_breakdown:
            # Step header
            step_title = f"Step {step.step_number}: {step.step_name}"
            if step.csa_clause_reference:
                step_title += f" ({step.csa_clause_reference})"
            elements.append(Paragraph(f"<b>{step_title}</b>", normal_style))

            # Explanation
            elements.append(Paragraph(step.explanation, normal_style))
            elements.append(Spacer(1, 0.05 * inch))

            # Calculation
            calc_text = f"<i>Calculation:</i> {step.calculation}"
            elements.append(Paragraph(calc_text, normal_style))

            # Result
            result_text = f"<b>Result:</b> {step.result}"
            elements.append(Paragraph(result_text, normal_style))
            elements.append(Spacer(1, 0.15 * inch))

    # Eligible Collateral
    if notice.eligible_collateral_summary:
        elements.append(Paragraph("ELIGIBLE COLLATERAL", heading_style))
        elements.append(Paragraph(notice.eligible_collateral_summary, normal_style))
        elements.append(Spacer(1, 0.3 * inch))

    # Deadlines
    if notice.notification_deadline or notice.delivery_deadline:
        elements.append(Paragraph("DEADLINES", heading_style))
        deadline_data = []
        if notice.notification_deadline:
            deadline_data.append(["Notification Deadline:", notice.notification_deadline])
        if notice.delivery_deadline:
            deadline_data.append(["Delivery Deadline:", notice.delivery_deadline])

        deadline_table = Table(deadline_data, colWidths=[2 * inch, 4 * inch])
        deadline_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ]
            )
        )
        elements.append(deadline_table)
        elements.append(Spacer(1, 0.3 * inch))

    # Legal Disclaimer
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph("LEGAL DISCLAIMER", heading_style))
    elements.append(Paragraph(notice.legal_disclaimer, small_style))

    # Footer
    elements.append(Spacer(1, 0.3 * inch))
    footer_text = f"<i>This is an automated margin call notice generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}. Please verify all calculations independently.</i>"
    elements.append(Paragraph(footer_text, small_style))

    # Build PDF
    doc.build(elements)

    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
