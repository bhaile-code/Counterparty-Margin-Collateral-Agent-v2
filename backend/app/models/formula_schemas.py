"""
Formula Pattern Schema Definitions

Defines data models for CSA formula pattern extraction and analysis.
These schemas capture the calculation logic patterns found in CSA documents.

Author: Clause Agent System
Created: 2025-11-09
"""

from typing import Optional, List, Dict, Union, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class FormulaPattern(BaseModel):
    """
    Individual formula pattern (e.g., delivery_amount, return_amount).

    Represents a specific calculation pattern identified in CSA clauses.
    """
    pattern_name: str = Field(
        description="Name of the pattern (e.g., 'delivery_amount', 'return_amount')"
    )
    pattern_type: str = Field(
        description="Type of aggregation pattern: 'greatest_of', 'sum_of', 'conditional', 'single_rating', 'other'"
    )
    components: List[str] = Field(
        default_factory=list,
        description="Components being aggregated (e.g., ['moodys_csa', 'sp_csa'])"
    )
    clause_text: str = Field(
        default="",
        description="Verbatim clause text from CSA document"
    )
    source_page: int = Field(
        default=0,
        description="Page number where this clause appears"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for pattern identification (0.0 to 1.0)"
    )
    variations_detected: List[str] = Field(
        default_factory=list,
        description="Notes on unusual or non-standard pattern elements"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="LLM reasoning for pattern classification"
    )

    @field_validator('pattern_type')
    @classmethod
    def validate_pattern_type(cls, v: str) -> str:
        """Ensure pattern_type is one of the expected values."""
        valid_types = {'greatest_of', 'sum_of', 'conditional', 'single_rating', 'other'}
        if v not in valid_types:
            # Allow it but note as 'other'
            return 'other'
        return v


class ThresholdStructure(BaseModel):
    """
    Threshold pattern details.

    Describes how thresholds are structured in the CSA
    (fixed, variable by rating, conditional, etc.)
    """
    structure_type: str = Field(
        description="Type of threshold structure: 'fixed', 'variable_by_rating', 'conditional', 'asymmetric'"
    )
    party_a_base: Union[float, str] = Field(
        description="Base threshold for Party A (can be numeric or 'infinity')"
    )
    party_b_base: Union[float, str] = Field(
        description="Base threshold for Party B (can be numeric or 'infinity')"
    )
    triggers: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Rating trigger definitions that modify thresholds"
    )
    source_clause: str = Field(
        default="",
        description="Verbatim threshold clause text"
    )
    source_page: int = Field(
        default=0,
        description="Page number for threshold clause"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in threshold structure identification"
    )

    @field_validator('structure_type')
    @classmethod
    def validate_structure_type(cls, v: str) -> str:
        """Ensure structure_type is one of the expected values."""
        valid_types = {'fixed', 'variable_by_rating', 'conditional', 'asymmetric', 'other'}
        if v not in valid_types:
            return 'other'
        return v


class CollateralHaircutStructure(BaseModel):
    """
    Haircut dependency pattern.

    Describes how collateral haircuts are determined
    (fixed percentages, rating-dependent, collateral-type dependent, etc.)
    """
    dependency_type: str = Field(
        description="Type of haircut dependency: 'fixed', 'rating_dependent', 'collateral_dependent', 'matrix'"
    )
    table_reference: str = Field(
        default="",
        description="Reference to the haircut table in CSA (e.g., 'Paragraph 11(e)(ii)')"
    )
    source_page: int = Field(
        default=0,
        description="Page number for haircut table"
    )
    varies_by: List[str] = Field(
        default_factory=list,
        description="Factors that affect haircut values (e.g., ['rating_scenario', 'collateral_type'])"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in haircut structure identification"
    )
    rating_scenarios: Optional[List[str]] = Field(
        default=None,
        description="List of rating scenarios if rating-dependent"
    )

    @field_validator('dependency_type')
    @classmethod
    def validate_dependency_type(cls, v: str) -> str:
        """Ensure dependency_type is one of the expected values."""
        valid_types = {'fixed', 'rating_dependent', 'collateral_dependent', 'matrix', 'other'}
        if v not in valid_types:
            return 'other'
        return v


class MTARules(BaseModel):
    """Minimum Transfer Amount rules structure."""
    party_a_mta: Union[float, str] = Field(
        description="Party A MTA value"
    )
    party_b_mta: Union[float, str] = Field(
        description="Party B MTA value"
    )
    structure_type: str = Field(
        default="fixed",
        description="'fixed', 'variable', or 'conditional'"
    )
    source_page: int = Field(
        default=0,
        description="Page number for MTA clause"
    )


class RoundingRules(BaseModel):
    """Rounding rules structure."""
    rounding_method: str = Field(
        description="'up', 'down', 'nearest'"
    )
    rounding_increment: Union[float, str] = Field(
        description="Rounding increment amount"
    )
    applies_to: List[str] = Field(
        default_factory=list,
        description="What amounts are rounded (e.g., ['delivery_amount', 'return_amount'])"
    )
    source_page: int = Field(
        default=0,
        description="Page number for rounding clause"
    )


class IndependentAmountRules(BaseModel):
    """Independent Amount rules structure."""
    has_independent_amount: bool = Field(
        description="Whether CSA includes independent amounts"
    )
    party_a_amount: Union[float, str, None] = Field(
        default=None,
        description="Party A independent amount if applicable"
    )
    party_b_amount: Union[float, str, None] = Field(
        default=None,
        description="Party B independent amount if applicable"
    )
    source_page: int = Field(
        default=0,
        description="Page number for independent amount clause"
    )


class FormulaPatternResult(BaseModel):
    """
    Complete formula pattern extraction result.

    Aggregates all extracted patterns and provides overall analysis
    of the CSA's calculation structure.
    """
    document_id: str = Field(
        description="Document identifier this pattern analysis belongs to"
    )
    extraction_timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO timestamp of when patterns were extracted"
    )
    patterns: Dict[str, FormulaPattern] = Field(
        default_factory=dict,
        description="Dictionary of patterns keyed by pattern_name"
    )
    threshold_structure: ThresholdStructure = Field(
        description="Threshold calculation structure"
    )
    haircut_structure: CollateralHaircutStructure = Field(
        description="Collateral haircut dependency structure"
    )
    independent_amount: Optional[IndependentAmountRules] = Field(
        default=None,
        description="Independent amount rules if present"
    )
    mta_rules: MTARules = Field(
        description="Minimum Transfer Amount rules"
    )
    rounding_rules: RoundingRules = Field(
        description="Rounding rules for calculations"
    )
    complexity_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall complexity score: 0.0 (simple) to 1.0 (complex)"
    )
    overall_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall confidence in pattern extraction"
    )
    agent_reasoning: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Reasoning chain from Clause Agent"
    )
    variations_summary: List[str] = Field(
        default_factory=list,
        description="Summary of non-standard patterns detected across all clauses"
    )

    def get_csa_type_label(self) -> str:
        """
        Generate a human-readable label for this CSA's pattern type.

        Returns:
            String label like "Dual Agency - Greatest Of" or "Single Rating"
        """
        if 'delivery_amount' not in self.patterns:
            return "Unknown"

        delivery_pattern = self.patterns['delivery_amount']

        if delivery_pattern.pattern_type == 'greatest_of':
            if len(delivery_pattern.components) >= 2:
                return "Dual Agency - Greatest Of"
            return "Multi-Component - Greatest Of"
        elif delivery_pattern.pattern_type == 'sum_of':
            return "Multi-Component - Sum Of"
        elif delivery_pattern.pattern_type == 'single_rating':
            return "Single Rating Agency"
        elif delivery_pattern.pattern_type == 'conditional':
            return "Conditional Logic"
        else:
            return "Custom Pattern"

    def assess_complexity_factors(self) -> Dict[str, Any]:
        """
        Break down complexity score into contributing factors.

        Returns:
            Dictionary with complexity factor analysis
        """
        factors = {
            "aggregation_complexity": 0.0,
            "threshold_complexity": 0.0,
            "haircut_complexity": 0.0,
            "overall_assessment": "Simple"
        }

        # Aggregation complexity
        if 'delivery_amount' in self.patterns:
            pattern_type = self.patterns['delivery_amount'].pattern_type
            component_count = len(self.patterns['delivery_amount'].components)

            if pattern_type in ['greatest_of', 'sum_of']:
                factors["aggregation_complexity"] = min(0.3 * component_count / 2, 0.3)
            elif pattern_type == 'conditional':
                factors["aggregation_complexity"] = 0.4

        # Threshold complexity
        if self.threshold_structure.structure_type == 'variable_by_rating':
            factors["threshold_complexity"] = 0.3
        elif self.threshold_structure.structure_type == 'conditional':
            factors["threshold_complexity"] = 0.4

        # Haircut complexity
        if self.haircut_structure.dependency_type == 'rating_dependent':
            factors["haircut_complexity"] = 0.3
        elif self.haircut_structure.dependency_type == 'matrix':
            factors["haircut_complexity"] = 0.4

        # Overall assessment
        total_complexity = sum([
            factors["aggregation_complexity"],
            factors["threshold_complexity"],
            factors["haircut_complexity"]
        ])

        if total_complexity < 0.3:
            factors["overall_assessment"] = "Simple"
        elif total_complexity < 0.6:
            factors["overall_assessment"] = "Moderate"
        else:
            factors["overall_assessment"] = "Complex"

        return factors

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "document_id": "csa_12345",
                "extraction_timestamp": "2025-11-09T10:30:00Z",
                "patterns": {
                    "delivery_amount": {
                        "pattern_name": "delivery_amount",
                        "pattern_type": "greatest_of",
                        "components": ["moodys_csa", "sp_csa"],
                        "clause_text": "The 'Delivery Amount' will equal the greatest of...",
                        "source_page": 5,
                        "confidence": 0.95,
                        "variations_detected": []
                    }
                },
                "threshold_structure": {
                    "structure_type": "fixed",
                    "party_a_base": "infinity",
                    "party_b_base": 0.0,
                    "source_clause": "Party A Threshold: Infinity...",
                    "source_page": 4,
                    "confidence": 0.98
                },
                "haircut_structure": {
                    "dependency_type": "rating_dependent",
                    "table_reference": "Paragraph 11(e)(ii)",
                    "source_page": 7,
                    "varies_by": ["rating_scenario", "collateral_type"],
                    "confidence": 0.92
                },
                "mta_rules": {
                    "party_a_mta": 50000.0,
                    "party_b_mta": 50000.0,
                    "structure_type": "fixed",
                    "source_page": 4
                },
                "rounding_rules": {
                    "rounding_method": "up",
                    "rounding_increment": 1000.0,
                    "applies_to": ["delivery_amount"],
                    "source_page": 4
                },
                "complexity_score": 0.45,
                "overall_confidence": 0.92,
                "variations_summary": []
            }
        }
