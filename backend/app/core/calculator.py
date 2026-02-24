"""
Core margin calculation engine - MUST BE DETERMINISTIC.

All functions in this module must produce identical results for identical inputs.
No randomness, no external dependencies that could affect calculations.
"""

import logging
import math
from typing import List, Tuple

from app.models.schemas import (
    CollateralItem,
    MarginCall,
    MarginCallAction,
    CalculationStep,
    Currency,
)
from app.utils.constants import is_infinite_threshold

# Set up logging for calculation steps
logger = logging.getLogger(__name__)


def round_up_to_increment(value: float, increment: float) -> float:
    """
    Round a value up to the nearest increment.

    Args:
        value: The value to round
        increment: The increment to round to

    Returns:
        The value rounded up to the nearest increment

    Example:
        round_up_to_increment(1,234,567.89, 10000) -> 1,240,000
    """
    if increment <= 0:
        raise ValueError("Increment must be greater than 0")
    return math.ceil(value / increment) * increment


def round_down_to_increment(value: float, increment: float) -> float:
    """
    Round a value down to the nearest increment.

    Args:
        value: The value to round
        increment: The increment to round to

    Returns:
        The value rounded down to the nearest increment

    Example:
        round_down_to_increment(1,234,567.89, 10000) -> 1,230,000
    """
    if increment <= 0:
        raise ValueError("Increment must be greater than 0")
    return math.floor(value / increment) * increment


def calculate_effective_collateral(
    posted_collateral: List[CollateralItem],
) -> Tuple[float, List[dict]]:
    """
    Calculate the effective value of posted collateral after applying haircuts.

    Args:
        posted_collateral: List of CollateralItem objects

    Returns:
        Tuple of (total_effective_value, breakdown_details)
    """
    effective_value = 0.0
    breakdown = []

    for item in posted_collateral:
        item_effective_value = item.market_value * (1 - item.haircut_rate)
        effective_value += item_effective_value

        breakdown.append(
            {
                "collateral_type": item.collateral_type.value,
                "market_value": item.market_value,
                "haircut_rate": item.haircut_rate,
                "haircut_amount": item.market_value * item.haircut_rate,
                "effective_value": item_effective_value,
            }
        )

        logger.debug(
            f"Collateral item: {item.collateral_type.value}, "
            f"Market value: ${item.market_value:,.2f}, "
            f"Haircut: {item.haircut_rate * 100:.2f}%, "
            f"Effective: ${item_effective_value:,.2f}"
        )

    return effective_value, breakdown


def calculate_margin_requirement(
    net_exposure: float,
    threshold: float,
    minimum_transfer_amount: float,
    rounding: float,
    posted_collateral: List[CollateralItem],
    independent_amount: float = 0.0,
    counterparty_name: str = None,
    csa_terms_id: str = None,
) -> MarginCall:
    """
    Core margin calculation logic - MUST BE DETERMINISTIC.

    This function implements the exact logic from PROJECT_CONTEXT.md:
    1. Calculate exposure above threshold
    2. Calculate effective posted collateral (with haircuts)
    3. Determine raw requirement
    4. Apply MTA check
    5. Apply rounding

    Args:
        net_exposure: Current net exposure to the counterparty
        threshold: Amount of exposure before collateral is required
        minimum_transfer_amount: Minimum amount that must be transferred (MTA)
        rounding: Rounding increment for calls
        posted_collateral: List of currently posted collateral items
        independent_amount: Additional collateral requirement (default: 0)
        counterparty_name: Name of counterparty (for reference)
        csa_terms_id: ID of CSA terms document (for reference)

    Returns:
        MarginCall object with action, amount, and detailed calculation steps

    Raises:
        ValueError: If any input parameters are invalid
    """
    # Input validation
    if threshold is not None and not is_infinite_threshold(threshold) and threshold < 0:
        raise ValueError("Threshold must be >= 0, None, or infinity")
    if minimum_transfer_amount < 0:
        raise ValueError("Minimum transfer amount must be >= 0")
    if rounding <= 0:
        raise ValueError("Rounding must be > 0")
    if independent_amount < 0:
        raise ValueError("Independent amount must be >= 0")

    calculation_steps = []
    step_number = 1

    # Handle infinite threshold - no collateral ever required
    # Business Logic: Party with infinite threshold NEVER posts collateral
    if threshold is None or is_infinite_threshold(threshold):
        logger.info(
            f"Infinite threshold for {counterparty_name or 'Unknown'}: "
            f"No collateral required regardless of exposure (${net_exposure:,.2f})"
        )

        calculation_steps.append(
            CalculationStep(
                step_number=step_number,
                description="Infinite threshold - no collateral ever required for this party",
                formula="threshold = ∞ → exposure_above_threshold = 0",
                inputs={"net_exposure": net_exposure, "threshold": "Infinity"},
                result=0.0,
                source_clause="CSA Paragraph 13 - Threshold Amount (Party has unlimited threshold)",
            )
        )

        return MarginCall(
            action=MarginCallAction.NO_ACTION,
            amount=0.0,
            currency=Currency.USD,
            net_exposure=net_exposure,
            threshold=math.inf,  # Store as infinity
            posted_collateral_items=posted_collateral,
            effective_collateral=0.0,
            exposure_above_threshold=0.0,
            calculation_steps=calculation_steps,
            counterparty_name=counterparty_name,
            csa_terms_id=csa_terms_id,
        )

    # Log start of calculation
    logger.info(
        f"Starting margin calculation for {counterparty_name or 'Unknown'}: "
        f"Exposure=${net_exposure:,.2f}, Threshold=${threshold:,.2f}, "
        f"MTA=${minimum_transfer_amount:,.2f}, Rounding=${rounding:,.2f}"
    )

    # Step 1: Calculate exposure above threshold
    exposure_above_threshold = max(net_exposure - threshold, 0)
    calculation_steps.append(
        CalculationStep(
            step_number=step_number,
            description="Calculate exposure above threshold",
            formula="max(net_exposure - threshold, 0)",
            inputs={"net_exposure": net_exposure, "threshold": threshold},
            result=exposure_above_threshold,
            source_clause="CSA Paragraph 13 - Threshold Amount",
        )
    )
    step_number += 1

    logger.info(f"Step 1: Exposure above threshold = ${exposure_above_threshold:,.2f}")

    # Step 2: Calculate posted collateral value after haircuts
    effective_collateral, collateral_breakdown = calculate_effective_collateral(
        posted_collateral
    )
    calculation_steps.append(
        CalculationStep(
            step_number=step_number,
            description="Calculate effective value of posted collateral (after haircuts)",
            formula="sum(market_value * (1 - haircut_rate)) for each collateral item",
            inputs={
                "posted_collateral": [
                    {
                        "type": item.collateral_type.value,
                        "market_value": item.market_value,
                        "haircut": item.haircut_rate,
                    }
                    for item in posted_collateral
                ]
            },
            result=effective_collateral,
            source_clause="CSA Paragraph 11 - Valuation and Haircuts",
        )
    )
    step_number += 1

    logger.info(f"Step 2: Effective collateral = ${effective_collateral:,.2f}")

    # Step 2.5: Add independent amount to exposure
    total_collateral_requirement = exposure_above_threshold + independent_amount
    if independent_amount > 0:
        calculation_steps.append(
            CalculationStep(
                step_number=step_number,
                description="Add independent amount to exposure",
                formula="exposure_above_threshold + independent_amount",
                inputs={
                    "exposure_above_threshold": exposure_above_threshold,
                    "independent_amount": independent_amount,
                },
                result=total_collateral_requirement,
                source_clause="CSA Paragraph 13 - Independent Amount",
            )
        )
        step_number += 1
        logger.info(
            f"Step 2.5: Total requirement with IA = ${total_collateral_requirement:,.2f}"
        )
    else:
        total_collateral_requirement = exposure_above_threshold

    # Step 3: Calculate raw collateral requirement
    collateral_required_raw = total_collateral_requirement - effective_collateral
    calculation_steps.append(
        CalculationStep(
            step_number=step_number,
            description="Calculate raw collateral requirement",
            formula="total_collateral_requirement - effective_collateral",
            inputs={
                "total_collateral_requirement": total_collateral_requirement,
                "effective_collateral": effective_collateral,
            },
            result=collateral_required_raw,
            source_clause="CSA Paragraph 3 - Credit Support Obligations",
        )
    )
    step_number += 1

    logger.info(f"Step 3: Raw collateral requirement = ${collateral_required_raw:,.2f}")

    # Step 4: Apply MTA check
    if abs(collateral_required_raw) < minimum_transfer_amount:
        calculation_steps.append(
            CalculationStep(
                step_number=step_number,
                description="Apply Minimum Transfer Amount (MTA) check - below threshold",
                formula="abs(collateral_required_raw) < minimum_transfer_amount",
                inputs={
                    "collateral_required_raw": collateral_required_raw,
                    "minimum_transfer_amount": minimum_transfer_amount,
                    "abs_value": abs(collateral_required_raw),
                },
                result=0.0,
                source_clause="CSA Paragraph 13 - Minimum Transfer Amount",
            )
        )

        logger.info(
            f"Step 4: MTA check - ${abs(collateral_required_raw):,.2f} < "
            f"${minimum_transfer_amount:,.2f} -> NO ACTION"
        )

        return MarginCall(
            action=MarginCallAction.NO_ACTION,
            amount=0.0,
            currency=Currency.USD,
            net_exposure=net_exposure,
            threshold=threshold,
            posted_collateral_items=posted_collateral,
            effective_collateral=effective_collateral,
            exposure_above_threshold=exposure_above_threshold,
            calculation_steps=calculation_steps,
            counterparty_name=counterparty_name,
            csa_terms_id=csa_terms_id,
        )

    calculation_steps.append(
        CalculationStep(
            step_number=step_number,
            description="Apply Minimum Transfer Amount (MTA) check - above threshold",
            formula="abs(collateral_required_raw) >= minimum_transfer_amount",
            inputs={
                "collateral_required_raw": collateral_required_raw,
                "minimum_transfer_amount": minimum_transfer_amount,
                "abs_value": abs(collateral_required_raw),
            },
            result=abs(collateral_required_raw),
            source_clause="CSA Paragraph 13 - Minimum Transfer Amount",
        )
    )
    step_number += 1

    logger.info(f"Step 4: MTA check passed - proceeding to rounding")

    # Step 5: Apply rounding
    if collateral_required_raw > 0:
        # We need to call for more collateral - round UP
        amount = round_up_to_increment(collateral_required_raw, rounding)
        action = MarginCallAction.CALL

        calculation_steps.append(
            CalculationStep(
                step_number=step_number,
                description="Round collateral call amount UP to nearest rounding increment",
                formula="ceil(collateral_required_raw / rounding) * rounding",
                inputs={
                    "collateral_required_raw": collateral_required_raw,
                    "rounding": rounding,
                },
                result=amount,
                source_clause="CSA Paragraph 13 - Rounding",
            )
        )

        logger.info(
            f"Step 5: CALL for collateral - ${collateral_required_raw:,.2f} "
            f"rounded up to ${amount:,.2f}"
        )
    else:
        # Counterparty can request return - round DOWN the absolute value
        amount = round_down_to_increment(abs(collateral_required_raw), rounding)
        action = MarginCallAction.RETURN

        calculation_steps.append(
            CalculationStep(
                step_number=step_number,
                description="Round collateral return amount DOWN to nearest rounding increment",
                formula="floor(abs(collateral_required_raw) / rounding) * rounding",
                inputs={
                    "collateral_required_raw": collateral_required_raw,
                    "abs_value": abs(collateral_required_raw),
                    "rounding": rounding,
                },
                result=amount,
                source_clause="CSA Paragraph 13 - Rounding",
            )
        )

        logger.info(
            f"Step 5: RETURN collateral - ${abs(collateral_required_raw):,.2f} "
            f"rounded down to ${amount:,.2f}"
        )

    # Create and return final margin call
    margin_call = MarginCall(
        action=action,
        amount=amount,
        currency=Currency.USD,
        net_exposure=net_exposure,
        threshold=threshold,
        posted_collateral_items=posted_collateral,
        effective_collateral=effective_collateral,
        exposure_above_threshold=exposure_above_threshold,
        calculation_steps=calculation_steps,
        counterparty_name=counterparty_name,
        csa_terms_id=csa_terms_id,
    )

    logger.info(f"✓ Calculation complete: {action.value} ${amount:,.2f}")

    return margin_call
