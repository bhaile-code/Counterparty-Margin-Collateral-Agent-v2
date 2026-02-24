"""
Test suite for the core calculation engine.

These tests verify that the margin calculation logic is deterministic and accurate.
All tests must pass with 100% accuracy.
"""

import pytest
from app.core.calculator import (
    calculate_margin_requirement,
    round_up_to_increment,
    round_down_to_increment,
    calculate_effective_collateral
)
from app.models.schemas import (
    CollateralItem,
    CollateralType,
    Currency,
    MarginCallAction
)


class TestRoundingFunctions:
    """Test rounding utility functions."""

    def test_round_up_to_increment(self):
        """Test rounding up to nearest increment."""
        assert round_up_to_increment(1234567.89, 10000) == 1240000
        assert round_up_to_increment(1000000, 10000) == 1000000
        assert round_up_to_increment(1000001, 10000) == 1010000
        assert round_up_to_increment(250001, 1000) == 251000
        assert round_up_to_increment(100, 50) == 100
        assert round_up_to_increment(101, 50) == 150

    def test_round_down_to_increment(self):
        """Test rounding down to nearest increment."""
        assert round_down_to_increment(1234567.89, 10000) == 1230000
        assert round_down_to_increment(1000000, 10000) == 1000000
        assert round_down_to_increment(1009999, 10000) == 1000000
        assert round_down_to_increment(250999, 1000) == 250000
        assert round_down_to_increment(100, 50) == 100
        assert round_down_to_increment(149, 50) == 100

    def test_rounding_with_zero_increment_raises_error(self):
        """Test that zero increment raises ValueError."""
        with pytest.raises(ValueError, match="Increment must be greater than 0"):
            round_up_to_increment(1000, 0)

        with pytest.raises(ValueError, match="Increment must be greater than 0"):
            round_down_to_increment(1000, 0)

    def test_rounding_with_negative_increment_raises_error(self):
        """Test that negative increment raises ValueError."""
        with pytest.raises(ValueError, match="Increment must be greater than 0"):
            round_up_to_increment(1000, -10)

        with pytest.raises(ValueError, match="Increment must be greater than 0"):
            round_down_to_increment(1000, -10)


class TestEffectiveCollateralCalculation:
    """Test effective collateral calculation with haircuts."""

    def test_cash_collateral_no_haircut(self):
        """Test that cash has zero haircut."""
        collateral = [
            CollateralItem(
                collateral_type=CollateralType.CASH,
                market_value=1000000,
                haircut_rate=0.0,
                currency=Currency.USD
            )
        ]
        effective_value, breakdown = calculate_effective_collateral(collateral)

        assert effective_value == 1000000
        assert len(breakdown) == 1
        assert breakdown[0]["effective_value"] == 1000000
        assert breakdown[0]["haircut_amount"] == 0

    def test_us_treasury_with_haircut(self):
        """Test US Treasury with 1% haircut."""
        collateral = [
            CollateralItem(
                collateral_type=CollateralType.US_TREASURY,
                market_value=1000000,
                haircut_rate=0.01,  # 1% haircut
                currency=Currency.USD
            )
        ]
        effective_value, breakdown = calculate_effective_collateral(collateral)

        assert effective_value == 990000  # 1M - 1%
        assert breakdown[0]["haircut_amount"] == 10000
        assert breakdown[0]["effective_value"] == 990000

    def test_multiple_collateral_items(self):
        """Test with multiple collateral types."""
        collateral = [
            CollateralItem(
                collateral_type=CollateralType.CASH,
                market_value=500000,
                haircut_rate=0.0,
                currency=Currency.USD
            ),
            CollateralItem(
                collateral_type=CollateralType.US_TREASURY,
                market_value=1000000,
                haircut_rate=0.01,
                currency=Currency.USD
            ),
            CollateralItem(
                collateral_type=CollateralType.CORPORATE_BONDS,
                market_value=500000,
                haircut_rate=0.05,  # 5% haircut
                currency=Currency.USD
            )
        ]
        effective_value, breakdown = calculate_effective_collateral(collateral)

        # Cash: 500K * 1.0 = 500K
        # UST: 1M * 0.99 = 990K
        # Corp: 500K * 0.95 = 475K
        # Total: 1,965K
        assert effective_value == 1965000
        assert len(breakdown) == 3


class TestScenario1BelowThreshold:
    """
    Scenario 1: Below Threshold
    Exposure: $1.8M, Threshold: $2M -> No call required
    """

    def test_exposure_below_threshold(self):
        """Test that no call is made when exposure is below threshold."""
        result = calculate_margin_requirement(
            net_exposure=1800000,  # $1.8M
            threshold=2000000,     # $2M
            minimum_transfer_amount=250000,
            rounding=10000,
            posted_collateral=[],
            counterparty_name="Test Bank"
        )

        assert result.action == MarginCallAction.NO_ACTION
        assert result.amount == 0.0
        assert result.exposure_above_threshold == 0.0

    def test_exposure_exactly_at_threshold(self):
        """Test that no call is made when exposure equals threshold."""
        result = calculate_margin_requirement(
            net_exposure=2000000,  # Exactly at threshold
            threshold=2000000,
            minimum_transfer_amount=250000,
            rounding=10000,
            posted_collateral=[]
        )

        assert result.action == MarginCallAction.NO_ACTION
        assert result.amount == 0.0


class TestScenario2MTAFilter:
    """
    Scenario 2: MTA Filter
    Exposure: $2.2M, Threshold: $2M, MTA: $250K -> $200K < MTA -> No call
    """

    def test_requirement_below_mta(self):
        """Test that no call is made when requirement is below MTA."""
        result = calculate_margin_requirement(
            net_exposure=2200000,   # $2.2M
            threshold=2000000,      # $2M
            minimum_transfer_amount=250000,  # $250K MTA
            rounding=10000,
            posted_collateral=[],
            counterparty_name="Test Bank"
        )

        # Exposure above threshold: $200K
        # This is below MTA of $250K, so no action
        assert result.action == MarginCallAction.NO_ACTION
        assert result.amount == 0.0
        assert result.exposure_above_threshold == 200000

    def test_requirement_exactly_at_mta(self):
        """Test edge case where requirement exactly equals MTA."""
        result = calculate_margin_requirement(
            net_exposure=2250000,   # $2.25M
            threshold=2000000,      # $2M
            minimum_transfer_amount=250000,  # $250K MTA
            rounding=10000,
            posted_collateral=[]
        )

        # Exposure above threshold: $250K
        # This equals MTA, so call should be made
        assert result.action == MarginCallAction.CALL
        assert result.amount == 250000  # Rounded to $250K

    def test_requirement_above_mta(self):
        """Test that call is made when requirement is above MTA."""
        result = calculate_margin_requirement(
            net_exposure=2300000,   # $2.3M
            threshold=2000000,      # $2M
            minimum_transfer_amount=250000,  # $250K MTA
            rounding=10000,
            posted_collateral=[]
        )

        # Exposure above threshold: $300K
        # This is above MTA, so call should be made
        assert result.action == MarginCallAction.CALL
        assert result.amount == 300000


class TestScenario3WithHaircuts:
    """
    Scenario 3: With Haircuts
    Exposure: $5M, Threshold: $2M, Posted: $1M UST with 1% haircut
    Effective posted: $990K, Call: $2.01M rounded to $2.01M
    """

    def test_call_with_haircut(self):
        """Test margin call calculation with collateral haircut."""
        posted_collateral = [
            CollateralItem(
                collateral_type=CollateralType.US_TREASURY,
                market_value=1000000,  # $1M
                haircut_rate=0.01,     # 1% haircut
                currency=Currency.USD
            )
        ]

        result = calculate_margin_requirement(
            net_exposure=5000000,   # $5M
            threshold=2000000,      # $2M
            minimum_transfer_amount=250000,
            rounding=10000,
            posted_collateral=posted_collateral,
            counterparty_name="Test Bank"
        )

        # Exposure above threshold: $5M - $2M = $3M
        # Effective collateral: $1M * 0.99 = $990K
        # Raw requirement: $3M - $990K = $2.01M
        # Rounded up to $2.01M (already at rounding increment)
        assert result.action == MarginCallAction.CALL
        assert result.exposure_above_threshold == 3000000
        assert result.effective_collateral == 990000
        assert result.amount == 2010000  # $2.01M

    def test_call_with_multiple_haircuts(self):
        """Test with different haircut rates on different collateral."""
        posted_collateral = [
            CollateralItem(
                collateral_type=CollateralType.CASH,
                market_value=500000,
                haircut_rate=0.0,
                currency=Currency.USD
            ),
            CollateralItem(
                collateral_type=CollateralType.US_TREASURY,
                market_value=1000000,
                haircut_rate=0.02,  # 2% haircut
                currency=Currency.USD
            )
        ]

        result = calculate_margin_requirement(
            net_exposure=4000000,
            threshold=2000000,
            minimum_transfer_amount=100000,
            rounding=10000,
            posted_collateral=posted_collateral
        )

        # Exposure above threshold: $2M
        # Effective collateral: $500K + ($1M * 0.98) = $500K + $980K = $1.48M
        # Raw requirement: $2M - $1.48M = $520K
        # Rounded up: $520K
        assert result.action == MarginCallAction.CALL
        assert result.effective_collateral == 1480000
        assert result.amount == 520000


class TestScenario4MultipleCollateralTypes:
    """
    Scenario 4: Multiple Collateral Types
    Mix of Cash (0% haircut) and Securities (various haircuts)
    """

    def test_mixed_collateral_portfolio(self):
        """Test calculation with diverse collateral types."""
        posted_collateral = [
            CollateralItem(
                collateral_type=CollateralType.CASH,
                market_value=1000000,
                haircut_rate=0.0,
                currency=Currency.USD
            ),
            CollateralItem(
                collateral_type=CollateralType.US_TREASURY,
                market_value=2000000,
                haircut_rate=0.01,
                currency=Currency.USD
            ),
            CollateralItem(
                collateral_type=CollateralType.GOVERNMENT_BONDS,
                market_value=1000000,
                haircut_rate=0.03,
                currency=Currency.USD
            ),
            CollateralItem(
                collateral_type=CollateralType.CORPORATE_BONDS,
                market_value=500000,
                haircut_rate=0.08,
                currency=Currency.USD
            )
        ]

        result = calculate_margin_requirement(
            net_exposure=8000000,
            threshold=1000000,
            minimum_transfer_amount=100000,
            rounding=10000,
            posted_collateral=posted_collateral
        )

        # Exposure above threshold: $8M - $1M = $7M
        # Effective collateral:
        #   - Cash: $1M * 1.0 = $1M
        #   - UST: $2M * 0.99 = $1.98M
        #   - Gov: $1M * 0.97 = $970K
        #   - Corp: $500K * 0.92 = $460K
        #   Total: $4.41M
        # Raw requirement: $7M - $4.41M = $2.59M
        # Rounded up: $2.59M
        assert result.action == MarginCallAction.CALL
        assert result.effective_collateral == 4410000
        assert result.amount == 2590000


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_exposure(self):
        """Test with zero exposure."""
        result = calculate_margin_requirement(
            net_exposure=0,
            threshold=1000000,
            minimum_transfer_amount=100000,
            rounding=10000,
            posted_collateral=[]
        )

        assert result.action == MarginCallAction.NO_ACTION
        assert result.amount == 0.0

    def test_negative_exposure_with_posted_collateral(self):
        """Test negative exposure (we owe counterparty) with posted collateral."""
        posted_collateral = [
            CollateralItem(
                collateral_type=CollateralType.CASH,
                market_value=1000000,
                haircut_rate=0.0,
                currency=Currency.USD
            )
        ]

        result = calculate_margin_requirement(
            net_exposure=-500000,  # Negative exposure
            threshold=1000000,
            minimum_transfer_amount=100000,
            rounding=10000,
            posted_collateral=posted_collateral
        )

        # Exposure above threshold: max(-500K - 1M, 0) = 0
        # Effective collateral: $1M
        # Raw requirement: 0 - $1M = -$1M
        # This exceeds MTA, so counterparty can request return
        # Rounded down: $1M
        assert result.action == MarginCallAction.RETURN
        assert result.amount == 1000000

    def test_zero_threshold(self):
        """Test with zero threshold (every dollar of exposure requires collateral)."""
        result = calculate_margin_requirement(
            net_exposure=500000,
            threshold=0,  # Zero threshold
            minimum_transfer_amount=100000,
            rounding=10000,
            posted_collateral=[]
        )

        assert result.action == MarginCallAction.CALL
        assert result.amount == 500000

    def test_independent_amount(self):
        """Test calculation with independent amount."""
        result = calculate_margin_requirement(
            net_exposure=3000000,
            threshold=2000000,
            minimum_transfer_amount=100000,
            rounding=10000,
            posted_collateral=[],
            independent_amount=500000  # Additional $500K required
        )

        # Exposure above threshold: $1M
        # Plus independent amount: $500K
        # Total requirement: $1.5M
        assert result.action == MarginCallAction.CALL
        assert result.amount == 1500000

    def test_large_numbers(self):
        """Test with very large numbers to ensure no overflow."""
        result = calculate_margin_requirement(
            net_exposure=100000000000,  # $100B
            threshold=50000000000,      # $50B
            minimum_transfer_amount=1000000,
            rounding=100000,
            posted_collateral=[]
        )

        assert result.action == MarginCallAction.CALL
        assert result.amount == 50000000000  # $50B

    def test_invalid_inputs(self):
        """Test that invalid inputs raise appropriate errors."""
        with pytest.raises(ValueError):
            calculate_margin_requirement(
                net_exposure=1000000,
                threshold=-1,  # Negative threshold
                minimum_transfer_amount=100000,
                rounding=10000,
                posted_collateral=[]
            )

        with pytest.raises(ValueError):
            calculate_margin_requirement(
                net_exposure=1000000,
                threshold=1000000,
                minimum_transfer_amount=-100000,  # Negative MTA
                rounding=10000,
                posted_collateral=[]
            )

        with pytest.raises(ValueError):
            calculate_margin_requirement(
                net_exposure=1000000,
                threshold=1000000,
                minimum_transfer_amount=100000,
                rounding=0,  # Zero rounding
                posted_collateral=[]
            )


class TestCalculationSteps:
    """Test that calculation steps are properly recorded."""

    def test_calculation_steps_are_recorded(self):
        """Verify that all calculation steps are captured."""
        result = calculate_margin_requirement(
            net_exposure=3000000,
            threshold=2000000,
            minimum_transfer_amount=100000,
            rounding=10000,
            posted_collateral=[]
        )

        # Should have multiple calculation steps
        assert len(result.calculation_steps) >= 4
        # Each step should have a description and result
        for step in result.calculation_steps:
            assert step.description
            assert isinstance(step.result, (int, float))
            assert step.step_number > 0

    def test_calculation_steps_have_source_clauses(self):
        """Verify that steps reference CSA clauses."""
        result = calculate_margin_requirement(
            net_exposure=3000000,
            threshold=2000000,
            minimum_transfer_amount=100000,
            rounding=10000,
            posted_collateral=[]
        )

        # At least some steps should have source clauses
        steps_with_source = [s for s in result.calculation_steps if s.source_clause]
        assert len(steps_with_source) > 0


class TestDeterminism:
    """Test that calculations are deterministic."""

    def test_same_inputs_produce_same_outputs(self):
        """Run the same calculation multiple times and verify identical results."""
        posted_collateral = [
            CollateralItem(
                collateral_type=CollateralType.US_TREASURY,
                market_value=1000000,
                haircut_rate=0.02,
                currency=Currency.USD
            )
        ]

        results = []
        for _ in range(10):
            result = calculate_margin_requirement(
                net_exposure=5000000,
                threshold=2000000,
                minimum_transfer_amount=100000,
                rounding=10000,
                posted_collateral=posted_collateral
            )
            results.append({
                "action": result.action,
                "amount": result.amount,
                "effective_collateral": result.effective_collateral
            })

        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result
