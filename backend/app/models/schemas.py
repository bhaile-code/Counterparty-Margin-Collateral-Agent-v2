"""Pydantic models for the margin collateral agent."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, TYPE_CHECKING, Any
from pydantic import BaseModel, Field, field_validator, field_serializer, model_validator
from app.utils.constants import normalize_threshold

if TYPE_CHECKING:
    from app.models.normalized_collateral import (
        NormalizedCollateral,
        NormalizedCollateralTable,
        StandardizedCollateralType,
    )


class Currency(str, Enum):
    """Supported currencies (MVP: USD only)."""

    USD = "USD"


class CollateralType(str, Enum):
    """Types of eligible collateral."""

    # Cash types
    CASH_USD = "CASH_USD"
    CASH_EUR = "CASH_EUR"
    CASH_GBP = "CASH_GBP"
    CASH_JPY = "CASH_JPY"

    # Securities
    US_TREASURY = "US_TREASURY"
    US_AGENCY = "US_AGENCY"
    CORPORATE_BONDS = "CORPORATE_BONDS"
    MORTGAGE_BACKED_SECURITIES = "MORTGAGE_BACKED_SECURITIES"
    ASSET_BACKED_SECURITIES = "ASSET_BACKED_SECURITIES"
    MUNICIPAL_BONDS = "MUNICIPAL_BONDS"
    FOREIGN_SOVEREIGN = "FOREIGN_SOVEREIGN"

    # Equities
    EQUITIES_LISTED = "EQUITIES_LISTED"
    EQUITIES_NON_LISTED = "EQUITIES_NON_LISTED"

    # Other
    MONEY_MARKET_FUNDS = "MONEY_MARKET_FUNDS"
    COMMODITIES = "COMMODITIES"
    OTHER = "OTHER"

    # Legacy types (for backward compatibility)
    CASH = "CASH"
    GOVERNMENT_BONDS = "GOVERNMENT_BONDS"


class MarginCallAction(str, Enum):
    """Possible margin call actions."""

    NO_ACTION = "NO_ACTION"
    CALL = "CALL"  # Request more collateral
    RETURN = "RETURN"  # Counterparty can request return


class CollateralItem(BaseModel):
    """Represents a piece of posted collateral."""

    collateral_type: CollateralType
    market_value: float = Field(
        gt=0, description="Current market value in base currency"
    )
    haircut_rate: float = Field(
        ge=0, le=1, description="Haircut rate (0-1, e.g., 0.02 for 2%)"
    )
    currency: Currency = Currency.USD
    description: Optional[str] = None

    # Maturity information for maturity-aware haircut selection
    maturity_date: Optional[datetime] = Field(
        None, description="Maturity date of the security (for bonds, securities)"
    )
    maturity_years: Optional[float] = Field(
        None,
        description="Maturity in years from valuation date (calculated or provided)",
    )

    @property
    def effective_value(self) -> float:
        """Calculate effective collateral value after haircut."""
        return self.market_value * (1 - self.haircut_rate)


class ParsedCollateralItem(BaseModel):
    """Represents a parsed collateral item from CSV import."""

    csv_row_number: int
    description: str
    market_value: float
    maturity_min: Optional[float] = None  # None = no lower bound
    maturity_max: Optional[float] = None  # None = no upper bound
    currency: str = "USD"
    valuation_scenario: Optional[str] = None
    parse_errors: List[str] = Field(default_factory=list)

    @property
    def maturity_display(self) -> str:
        """Human-readable maturity range"""
        if self.maturity_min is None and self.maturity_max is None:
            return "All maturities"
        elif self.maturity_min is None:
            return f"<= {self.maturity_max} years"
        elif self.maturity_max is None:
            return f">= {self.maturity_min} years"
        elif self.maturity_min == self.maturity_max:
            return f"{self.maturity_min} years"
        else:
            return f"{self.maturity_min}-{self.maturity_max} years"

    def matches_maturity_bucket(
        self,
        bucket_min: Optional[float],
        bucket_max: Optional[float]
    ) -> bool:
        """Check if this range overlaps with a maturity bucket"""
        # Handle "all maturities" case
        if self.maturity_min is None and self.maturity_max is None:
            return True

        # Check for overlap between ranges
        user_min = self.maturity_min or 0
        user_max = self.maturity_max or float('inf')
        bucket_min = bucket_min or 0
        bucket_max = bucket_max or float('inf')

        return user_min <= bucket_max and user_max >= bucket_min


class MatchedCollateralItem(BaseModel):
    """Represents a collateral item matched to CSA collateral descriptions."""

    csv_row_number: int
    csv_description: str
    market_value: float
    maturity_min: Optional[float] = None
    maturity_max: Optional[float] = None
    currency: str = "USD"
    valuation_scenario: str

    # AI Matching results
    matched_csa_description: Optional[str] = None
    matched_standardized_type: Optional[str] = None
    matched_maturity_bucket_min: Optional[float] = None
    matched_maturity_bucket_max: Optional[float] = None
    match_confidence: float = 0.0  # 0.0 to 1.0
    match_reasoning: str = ""

    # Haircut lookup
    haircut_rate: Optional[float] = None  # None if not found
    haircut_source: str = "auto"  # "auto", "default_zero", "manual_override"
    warnings: List[str] = Field(default_factory=list)

    @property
    def maturity_display(self) -> str:
        """Human-readable user maturity range"""
        if self.maturity_min is None and self.maturity_max is None:
            return "All maturities"
        elif self.maturity_min is None:
            return f"<= {self.maturity_max} years"
        elif self.maturity_max is None:
            return f">= {self.maturity_min} years"
        elif self.maturity_min == self.maturity_max:
            return f"{self.maturity_min} years"
        else:
            return f"{self.maturity_min}-{self.maturity_max} years"

    @property
    def matched_bucket_display(self) -> str:
        """Human-readable matched bucket range"""
        if self.matched_maturity_bucket_min is None and self.matched_maturity_bucket_max is None:
            return "All maturities"
        elif self.matched_maturity_bucket_min is None:
            return f"<= {self.matched_maturity_bucket_max} years"
        elif self.matched_maturity_bucket_max is None:
            return f">= {self.matched_maturity_bucket_min} years"
        elif self.matched_maturity_bucket_min == self.matched_maturity_bucket_max:
            return f"{self.matched_maturity_bucket_min} years"
        else:
            return f"{self.matched_maturity_bucket_min}-{self.matched_maturity_bucket_max} years"

    @property
    def effective_value(self) -> float:
        """Calculate effective collateral value after haircut."""
        haircut = self.haircut_rate or 0.0
        return self.market_value * (1 - haircut)


class CSATerms(BaseModel):
    """Core terms extracted from a CSA document."""

    # Party identification
    party_a: Optional[str] = None
    party_b: Optional[str] = None

    # Party-specific margin terms
    party_a_threshold: Optional[float] = Field(
        None, description="Party A threshold - amount of exposure before collateral is required (can be 0, finite, or inf)"
    )
    party_b_threshold: Optional[float] = Field(
        None, description="Party B threshold - amount of exposure before collateral is required (can be 0, finite, or inf)"
    )
    party_a_minimum_transfer_amount: Optional[float] = Field(
        None, description="Party A minimum transfer amount (can be 0, finite, or inf)"
    )
    party_b_minimum_transfer_amount: Optional[float] = Field(
        None, description="Party B minimum transfer amount (can be 0, finite, or inf)"
    )
    party_a_independent_amount: Optional[float] = Field(
        None, description="Party A independent amount - additional collateral requirement (can be 0, finite, or inf)"
    )
    party_b_independent_amount: Optional[float] = Field(
        None, description="Party B independent amount - additional collateral requirement (can be 0, finite, or inf)"
    )
    rounding: float = Field(gt=0, description="Rounding increment for calls")
    currency: Currency = Currency.USD

    # Normalized collateral reference (REQUIRED)
    normalized_collateral_id: str = Field(
        description="Reference to normalized collateral table for this document"
    )

    # Eligible collateral types with maturity-aware haircuts
    # Note: Using generic List to avoid circular dependency with NormalizedCollateral
    # Items are accessed via getattr() in the matcher service
    eligible_collateral: List = Field(
        default_factory=list,
        description="List of NormalizedCollateral items with haircut rates and maturity buckets",
    )

    # Provenance tracking (will be populated by ADE)
    valuation_agent: Optional[str] = None
    effective_date: Optional[datetime] = None

    # Confidence scores (from ADE extraction)
    confidence_scores: Optional[dict] = Field(
        default=None, description="Confidence scores for each extracted field"
    )

    # Document source
    source_document_id: Optional[str] = None
    source_pages: Optional[dict] = Field(
        default=None, description="Mapping of fields to source page numbers"
    )

    @field_validator(
        'party_a_threshold',
        'party_b_threshold',
        'party_a_minimum_transfer_amount',
        'party_b_minimum_transfer_amount',
        'party_a_independent_amount',
        'party_b_independent_amount',
        mode='before'
    )
    @classmethod
    def normalize_threshold_values(cls, v):
        """
        Normalize special threshold values from CSA documents.

        Business Logic:
        - "Infinity" / "Unlimited" → float('inf') - No margin call ever triggered
        - "N/A" / "0" → 0.0 - Margin call triggers on any exposure
        - Numeric values → converted to float

        Args:
            v: Raw threshold value from CSA document

        Returns:
            float: Normalized threshold (0.0, finite number, or inf)
        """
        return normalize_threshold(v)

    @field_serializer(
        'party_a_threshold',
        'party_b_threshold',
        'party_a_minimum_transfer_amount',
        'party_b_minimum_transfer_amount',
        'party_a_independent_amount',
        'party_b_independent_amount',
        when_used='json'
    )
    def serialize_threshold_values(self, value: Optional[float]) -> Optional[float]:
        """
        Serialize threshold values to JSON-compatible format.

        Converts float('inf') to "Infinity" string for JSON serialization.
        This ensures infinity values survive the JSON round-trip.

        Args:
            value: Threshold value (can be 0, finite, inf, or None)

        Returns:
            Same value (InfinityEncoder will handle inf -> "Infinity" conversion)
        """
        # Return as-is; InfinityEncoder will handle the inf -> "Infinity" conversion
        return value

    def get_collateral_by_type(
        self, collateral_type: "StandardizedCollateralType", rating_event: str
    ) -> Optional["NormalizedCollateral"]:
        """
        Find a specific collateral item by type and rating event.

        Args:
            collateral_type: Standardized collateral type
            rating_event: Rating event name

        Returns:
            Matching NormalizedCollateral, or None if not found
        """
        for item in self.eligible_collateral:
            if (
                item.standardized_type == collateral_type
                and item.rating_event == rating_event
            ):
                return item
        return None

    def get_haircut_for_maturity(
        self,
        collateral_type: "StandardizedCollateralType",
        rating_event: str,
        maturity_years: Optional[float],
    ) -> Optional[float]:
        """
        Get the appropriate haircut for given collateral type and maturity.

        Args:
            collateral_type: Standardized collateral type
            rating_event: Rating event name
            maturity_years: Maturity in years (None for non-maturity-based)

        Returns:
            Haircut rate, or None if no matching collateral found
        """
        collateral = self.get_collateral_by_type(collateral_type, rating_event)
        if not collateral:
            return None

        # If no maturity provided or no maturity buckets, use flat haircut
        if maturity_years is None or not collateral.maturity_buckets:
            return collateral.flat_haircut

        # Find matching maturity bucket
        return collateral.get_haircut_for_maturity(maturity_years)

    def load_normalized_collateral(self) -> Optional["NormalizedCollateralTable"]:
        """
        Load the full normalized collateral table for this CSA.

        Returns:
            NormalizedCollateralTable object, or None if not found
        """
        from app.utils.file_storage import FileStorage
        from app.config import settings

        return FileStorage.load_normalized_collateral(
            self.normalized_collateral_id, settings.normalized_collateral_dir
        )

    def get_haircut_for_collateral_range(
        self,
        csa_description: str,
        rating_event: str,
        maturity_min: Optional[float],
        maturity_max: Optional[float]
    ) -> tuple[Optional[float], Optional[float], Optional[float], List[str]]:
        """
        Look up haircut from normalized collateral table using maturity range.

        Args:
            csa_description: Exact match to collateral_type_display
            rating_event: e.g., "Moody's Second Trigger"
            maturity_min: Minimum years, None = no lower bound
            maturity_max: Maximum years, None = no upper bound

        Returns:
            (haircut_rate, bucket_min, bucket_max, warnings)
            - haircut_rate: 0.02 for 2%, or None if not found
            - bucket_min/max: Matched bucket range
            - warnings: List of warning messages
        """
        warnings = []

        # Find matching NormalizedCollateral by base_description and rating_event
        matching_collateral = None
        for nc in self.eligible_collateral:
            # NormalizedCollateral uses base_description, not collateral_type_display
            if getattr(nc, 'base_description', '') == csa_description:
                # Check if this item matches the requested rating_event
                nc_rating_event = getattr(nc, 'rating_event', 'No Rating Event')
                if nc_rating_event == rating_event:
                    matching_collateral = nc
                    break

        if not matching_collateral:
            warnings.append(f"Collateral '{csa_description}' with rating event '{rating_event}' not found in CSA")
            return (None, None, None, warnings)

        # Get maturity buckets - it's a list directly on the NormalizedCollateral
        buckets = getattr(matching_collateral, 'maturity_buckets', [])

        if not buckets:
            warnings.append(f"No maturity buckets for rating event '{rating_event}'")
            return (None, None, None, warnings)

        # Handle "all maturities" case - use most conservative haircut
        if maturity_min is None and maturity_max is None:
            max_haircut_bucket = max(buckets, key=lambda b: b.haircut)
            # No warning needed - blank maturity fields represent "all maturities" by design
            return (
                max_haircut_bucket.haircut,
                max_haircut_bucket.min_years,
                max_haircut_bucket.max_years,
                warnings
            )

        # Find overlapping maturity buckets
        user_min = maturity_min or 0
        user_max = maturity_max or float('inf')

        overlapping_buckets = []
        for bucket in buckets:
            bucket_min = bucket.min_years or 0
            bucket_max = bucket.max_years or float('inf')

            # Check for overlap
            if user_min <= bucket_max and user_max >= bucket_min:
                overlapping_buckets.append(bucket)

        if not overlapping_buckets:
            warnings.append(
                f"No maturity bucket matches range {maturity_min}-{maturity_max} years"
            )
            return (None, None, None, warnings)

        # If multiple buckets overlap, use the one with highest haircut (conservative)
        best_bucket = max(overlapping_buckets, key=lambda b: b.haircut)

        if len(overlapping_buckets) > 1:
            warnings.append(
                f"Range spans multiple buckets, using most conservative haircut ({best_bucket.haircut*100:.1f}%)"
            )

        return (
            best_bucket.haircut,
            best_bucket.min_years,
            best_bucket.max_years,
            warnings
        )


class CalculationStep(BaseModel):
    """Represents a single step in the margin calculation."""

    step_number: int
    description: str
    formula: Optional[str] = None
    inputs: dict
    result: float
    source_clause: Optional[str] = Field(
        None, description="Reference to CSA clause that defines this step"
    )


class MarginCall(BaseModel):
    """Result of a margin calculation."""

    action: MarginCallAction
    amount: float = Field(ge=0, description="Amount to call or return")
    currency: Currency = Currency.USD
    calculation_date: datetime = Field(default_factory=datetime.utcnow)

    # Detailed breakdown
    net_exposure: float
    threshold: float
    posted_collateral_items: List[CollateralItem]
    effective_collateral: float
    exposure_above_threshold: float

    # Calculation steps for transparency
    calculation_steps: List[CalculationStep] = Field(default_factory=list)

    # References
    csa_terms_id: Optional[str] = None
    counterparty_name: Optional[str] = None


class CalculationBreakdownStep(BaseModel):
    """Detailed breakdown of a single calculation step with citations."""

    step_number: int
    step_name: str
    explanation: str = Field(
        description="Clear explanation of what this step does and why"
    )
    csa_clause_reference: Optional[str] = Field(
        None, description="CSA clause reference (e.g., 'Section 3(a)')"
    )
    source_page: Optional[int] = Field(None, description="Source document page number")
    calculation: str = Field(description="Formula with actual values")
    result: str = Field(description="Result with interpretation")


class AuditTrailEvent(BaseModel):
    """Single event in the audit trail."""

    timestamp: str = Field(description="ISO 8601 timestamp")
    event: str = Field(description="Event description")
    details: str = Field(description="Additional context")


class MarginCallExplanation(BaseModel):
    """LLM-generated explanation of a margin call with citations."""

    # Core explanation
    narrative: str = Field(
        description="Comprehensive 3-5 paragraph explanation with citations"
    )
    key_factors: List[str] = Field(
        default_factory=list,
        description="3-5 key factors that drove this calculation result",
    )
    calculation_breakdown: List[CalculationBreakdownStep] = Field(
        default_factory=list,
        description="Step-by-step calculation analysis with citations",
    )
    audit_trail: List[AuditTrailEvent] = Field(
        default_factory=list, description="Chronological event log with timestamps"
    )

    # Citations and references
    citations: Dict[str, Optional[int]] = Field(
        default_factory=dict,
        description="Mapping of CSA clauses to page numbers (None if page unknown)",
    )

    # Assessment and recommendations
    risk_assessment: Optional[str] = Field(
        None, description="Assessment of collateral position and risks"
    )
    next_steps: Optional[str] = Field(
        None, description="Recommended next actions for operations"
    )

    # Metadata
    generated_at: str = Field(description="ISO 8601 timestamp when generated")
    llm_model: str = Field(description="LLM model used for generation")
    document_id: str = Field(description="Source CSA document ID")
    margin_call_action: str = Field(
        description="Margin call action (CALL/RETURN/NO_ACTION)"
    )
    margin_call_amount: float = Field(ge=0, description="Margin call amount")
    counterparty_name: str = Field(description="Counterparty name")


class ExplanationResponse(BaseModel):
    """API response for explanation generation."""

    status: str = "success"
    explanation: MarginCallExplanation
    message: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    """Response after uploading a CSA document."""

    document_id: str
    filename: str
    file_size: int
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = "uploaded"


class DocumentParseResponse(BaseModel):
    """Response after parsing a document with ADE."""

    document_id: str
    parse_id: str
    status: str
    page_count: Optional[int] = None
    parsed_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentExtractionResponse(BaseModel):
    """Response after extracting fields from a parsed document."""

    document_id: str
    extraction_id: str
    csa_terms: CSATerms
    status: str
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


class ProcessingStatus(BaseModel):
    """Processing status for a document across all pipeline stages."""

    uploaded: bool = Field(description="Document uploaded successfully")
    parsed: bool = Field(description="Document parsed with ADE")
    extracted: bool = Field(description="Fields extracted with ADE")
    normalized: bool = Field(description="Collateral normalized with AI")
    mapped_to_csa_terms: bool = Field(description="Mapped to CSATerms model")
    has_calculations: bool = Field(description="At least one calculation exists")


class ArtifactIds(BaseModel):
    """IDs of artifacts generated during document processing."""

    parse_id: Optional[str] = None
    extraction_id: Optional[str] = None
    normalized_collateral_id: Optional[str] = None
    csa_terms_id: Optional[str] = None
    calculation_ids: List[str] = Field(default_factory=list)


class DocumentDetailResponse(BaseModel):
    """Detailed information about a document and its processing status."""

    document_id: str
    filename: str
    file_size: int
    uploaded_at: datetime
    processing_status: ProcessingStatus
    artifact_ids: ArtifactIds
    errors: List[str] = Field(
        default_factory=list, description="Any processing errors encountered"
    )


class MarginCallNotice(BaseModel):
    """Structured margin call notice for export."""

    calculation_id: str
    document_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # Counterparty information
    party_a: str = Field(description="Party A (typically the firm)")
    party_b: str = Field(description="Party B (counterparty)")

    # Exposure and collateral summary
    current_exposure: float = Field(description="Current mark-to-market exposure")
    threshold: float = Field(description="Collateral threshold from CSA")
    posted_collateral_value: float = Field(
        description="Current posted collateral (after haircuts)"
    )
    independent_amount: float = Field(
        default=0, description="Independent amount requirement"
    )

    # Margin call details
    margin_call_action: MarginCallAction = Field(
        description="Required action (CALL/RETURN/NO_ACTION)"
    )
    margin_call_amount: float = Field(description="Amount to be called or returned")
    delivery_amount: float = Field(
        description="Actual delivery amount (after rounding)"
    )

    # Timeline
    valuation_date: str = Field(description="Valuation date for this calculation")
    notification_deadline: Optional[str] = Field(
        None, description="Deadline for notification"
    )
    delivery_deadline: Optional[str] = Field(None, description="Deadline for delivery")

    # Calculation details
    calculation_breakdown: List[CalculationBreakdownStep] = Field(
        default_factory=list, description="Step-by-step calculation"
    )

    # Eligible collateral
    eligible_collateral_summary: Optional[str] = Field(
        None, description="Summary of acceptable collateral types"
    )

    # Legal
    legal_disclaimer: str = Field(
        default="This margin call notice is generated based on the terms of the Credit Support Annex (CSA) agreement. Please review the calculation details and respond by the specified deadline.",
        description="Legal disclaimer text",
    )
