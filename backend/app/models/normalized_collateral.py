"""
Normalized collateral data models.

This module defines Pydantic models for storing collateral data after
AI-powered normalization. The normalization process extracts structured
information from raw ADE extraction output, including:
- Standardized collateral types
- Maturity bucket parsing
- Rating event mapping
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class StandardizedCollateralType(str, Enum):
    """Standardized collateral type categories."""

    CASH_USD = "CASH_USD"
    CASH_EUR = "CASH_EUR"
    CASH_GBP = "CASH_GBP"
    CASH_JPY = "CASH_JPY"
    CASH_OTHER = "CASH_OTHER"

    US_TREASURY = "US_TREASURY"
    US_AGENCY = "US_AGENCY"
    US_AGENCY_MBS = "US_AGENCY_MBS"  # Mortgage-backed securities

    GOVERNMENT_BONDS = "GOVERNMENT_BONDS"
    CORPORATE_BONDS = "CORPORATE_BONDS"
    COMMERCIAL_PAPER = "COMMERCIAL_PAPER"

    EQUITIES = "EQUITIES"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"  # Requires user review


class MaturityBucket(BaseModel):
    """
    Represents a maturity bucket with specific haircut/valuation rates.

    Example: For "99% (1-2yr), 98% (2-3yr)", this would create two buckets:
    - MaturityBucket(min_years=1, max_years=2, valuation_percentage=0.99, haircut=0.01)
    - MaturityBucket(min_years=2, max_years=3, valuation_percentage=0.98, haircut=0.02)
    """

    min_years: Optional[float] = Field(
        None,
        description="Minimum maturity in years (inclusive). None means no lower bound.",
    )
    max_years: Optional[float] = Field(
        None,
        description="Maximum maturity in years (inclusive). None means no upper bound.",
    )
    valuation_percentage: float = Field(
        ge=0.0,
        le=1.0,
        description="Valuation percentage as decimal (e.g., 0.98 for 98%)",
    )
    haircut: float = Field(
        ge=0.0, le=1.0, description="Haircut rate as decimal (e.g., 0.02 for 2%)"
    )
    original_text: Optional[str] = Field(
        None, description="Original text this bucket was parsed from (e.g., '1-2yr')"
    )

    def matches_maturity(self, years: float) -> bool:
        """Check if a given maturity (in years) falls within this bucket."""
        if self.min_years is not None and years < self.min_years:
            return False
        if self.max_years is not None and years > self.max_years:
            return False
        return True


class NormalizedCollateral(BaseModel):
    """
    Normalized representation of an eligible collateral type.

    This model represents a single row from the eligible collateral table
    after AI-powered normalization and structuring.
    """

    standardized_type: StandardizedCollateralType = Field(
        description="Standardized collateral type category"
    )

    base_description: str = Field(
        description="Original description from ADE extraction"
    )

    maturity_buckets: List[MaturityBucket] = Field(
        default_factory=list,
        description="Maturity buckets with corresponding haircuts. Empty if no maturity-based haircuts.",
    )

    rating_event: Optional[str] = Field(
        None,
        description="Rating event this collateral row applies to (e.g., 'Moody's First Trigger Event')",
    )

    # For collateral without maturity buckets (e.g., cash)
    flat_valuation_percentage: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Single valuation percentage for collateral without maturity buckets",
    )

    flat_haircut: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Single haircut for collateral without maturity buckets",
    )

    # Metadata
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="AI model confidence in the normalization (0-1)",
    )

    notes: Optional[str] = Field(
        None, description="Additional notes or warnings about this collateral type"
    )

    def get_haircut_for_maturity(self, years: float) -> Optional[float]:
        """
        Get the appropriate haircut for a given maturity.

        Args:
            years: Maturity in years

        Returns:
            Haircut rate, or None if no matching bucket found
        """
        if not self.maturity_buckets:
            return self.flat_haircut

        for bucket in self.maturity_buckets:
            if bucket.matches_maturity(years):
                return bucket.haircut

        return None

    def get_valuation_for_maturity(self, years: float) -> Optional[float]:
        """
        Get the appropriate valuation percentage for a given maturity.

        Args:
            years: Maturity in years

        Returns:
            Valuation percentage, or None if no matching bucket found
        """
        if not self.maturity_buckets:
            return self.flat_valuation_percentage

        for bucket in self.maturity_buckets:
            if bucket.matches_maturity(years):
                return bucket.valuation_percentage

        return None


class NormalizedCollateralTable(BaseModel):
    """
    Complete normalized collateral table for a CSA document.

    This represents the full eligible collateral schedule after normalization,
    organized by rating events.
    """

    document_id: str = Field(description="Source document identifier")

    extraction_id: str = Field(description="Source extraction identifier")

    rating_events: List[str] = Field(
        default_factory=list,
        description="List of rating event columns (e.g., ['No Rating Event', 'Rating Event A'])",
    )

    collateral_items: List[NormalizedCollateral] = Field(
        default_factory=list, description="List of normalized collateral items"
    )

    normalized_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when normalization was performed",
    )

    normalization_model: Optional[str] = Field(
        None,
        description="AI model used for normalization (e.g., 'claude-3-haiku-20240307')",
    )

    normalization_metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata about the normalization process",
    )

    def get_collateral_by_type_and_event(
        self, collateral_type: StandardizedCollateralType, rating_event: str
    ) -> Optional[NormalizedCollateral]:
        """
        Find a specific collateral item by type and rating event.

        Args:
            collateral_type: Standardized collateral type
            rating_event: Rating event name

        Returns:
            Matching NormalizedCollateral, or None if not found
        """
        for item in self.collateral_items:
            if (
                item.standardized_type == collateral_type
                and item.rating_event == rating_event
            ):
                return item
        return None

    def get_all_types(self) -> List[StandardizedCollateralType]:
        """Get list of all unique standardized collateral types in this table."""
        return list(set(item.standardized_type for item in self.collateral_items))
