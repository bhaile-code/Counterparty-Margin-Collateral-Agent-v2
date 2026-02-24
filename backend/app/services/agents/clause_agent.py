"""
ClauseAgent - Formula Pattern Extraction from CSA Documents

Implements multi-step reasoning chain to extract and analyze:
1. Delivery Amount formula patterns (greatest_of, sum_of, conditional, etc.)
2. Return Amount formula patterns
3. Threshold structures (fixed, variable_by_rating, conditional)
4. Collateral haircut dependencies (fixed, rating_dependent, matrix)
5. MTA, rounding, and independent amount rules

Author: Clause Agent System
Created: 2025-11-09
"""

import time
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.services.agents.base_agent import BaseNormalizerAgent
from app.models.agent_schemas import AgentResult
from app.models.formula_schemas import (
    FormulaPattern,
    ThresholdStructure,
    CollateralHaircutStructure,
    MTARules,
    RoundingRules,
    IndependentAmountRules,
    FormulaPatternResult
)
from app.models.schemas import CSATerms


class ClauseAgent(BaseNormalizerAgent):
    """
    Specialized agent for extracting formula patterns from CSA documents.

    Capabilities:
    - Identify aggregation patterns (greatest_of, sum_of, conditional)
    - Analyze threshold structures and rating triggers
    - Map collateral haircut dependencies
    - Extract MTA and rounding rules
    - Assess CSA complexity
    """

    def __init__(self, api_key: str):
        super().__init__(api_key)

    async def extract_patterns(
        self,
        document_id: str,
        ade_extraction: Dict[str, Any],
        csa_terms: CSATerms,
        document_context: Optional[Dict[str, Any]] = None
    ) -> FormulaPatternResult:
        """
        Main pattern extraction method.

        Args:
            document_id: Document identifier
            ade_extraction: ADE extraction result with extracted_fields and provenance
            csa_terms: Normalized CSA terms from existing pipeline
            document_context: Optional parsed document with chunks for additional context

        Returns:
            FormulaPatternResult with all extracted patterns
        """
        start_time = time.time()
        self._clear_reasoning_chain()

        # Extract data from ADE extraction
        extracted_fields = ade_extraction.get("extracted_fields", {})
        provenance = ade_extraction.get("provenance", {})
        column_info = extracted_fields.get("column_info", {})
        clauses = extracted_fields.get("clauses_to_collect", {})

        # Step 1: Extract Delivery Amount pattern (uses rating column analysis)
        step1_start = time.time()
        delivery_pattern = await self._extract_delivery_amount_pattern(
            extracted_fields,
            column_info,
            csa_terms,
            provenance,
            clauses
        )
        step1_duration = time.time() - step1_start

        self._add_reasoning_step(
            step_number=1,
            step_name="extract_delivery_amount_pattern",
            input_data={"column_info": column_info, "csa_terms": "CSATerms object"},
            output_data=delivery_pattern.dict(),
            reasoning=f"Analyzed rating columns and CSA structure to identify delivery amount pattern type: {delivery_pattern.pattern_type}",
            model_used=self.sonnet_model,
            confidence=delivery_pattern.confidence,
            duration_seconds=step1_duration
        )

        # Step 2: Extract Return Amount pattern (typically mirrors delivery)
        step2_start = time.time()
        return_pattern = await self._extract_return_amount_pattern(
            delivery_pattern,
            extracted_fields,
            csa_terms,
            provenance,
            clauses
        )
        step2_duration = time.time() - step2_start

        self._add_reasoning_step(
            step_number=2,
            step_name="extract_return_amount_pattern",
            input_data={"delivery_pattern_type": delivery_pattern.pattern_type},
            output_data=return_pattern.dict(),
            reasoning=f"Inferred return amount pattern based on delivery pattern: {return_pattern.pattern_type}",
            model_used="rule-based",
            confidence=return_pattern.confidence,
            duration_seconds=step2_duration
        )

        # Step 3: Analyze threshold structure
        step3_start = time.time()
        threshold_structure = await self._analyze_threshold_structure(
            extracted_fields,
            csa_terms,
            provenance
        )
        step3_duration = time.time() - step3_start

        self._add_reasoning_step(
            step_number=3,
            step_name="analyze_threshold_structure",
            input_data={"party_a_threshold": str(csa_terms.party_a_threshold), "party_b_threshold": str(csa_terms.party_b_threshold)},
            output_data=threshold_structure.dict(),
            reasoning=f"Analyzed threshold values and identified structure type: {threshold_structure.structure_type}",
            model_used="rule-based",
            confidence=threshold_structure.confidence,
            duration_seconds=step3_duration
        )

        # Step 4: Analyze haircut structure
        step4_start = time.time()
        haircut_structure = await self._analyze_haircut_structure(
            extracted_fields,
            column_info,
            csa_terms,
            provenance
        )
        step4_duration = time.time() - step4_start

        self._add_reasoning_step(
            step_number=4,
            step_name="analyze_haircut_structure",
            input_data={"column_count": column_info.get("valuation_column_count", 0)},
            output_data=haircut_structure.dict(),
            reasoning=f"Analyzed collateral haircut dependencies: {haircut_structure.dependency_type}",
            model_used=self.sonnet_model,
            confidence=haircut_structure.confidence,
            duration_seconds=step4_duration
        )

        # Step 5: Extract MTA, rounding, and independent amount rules
        step5_start = time.time()
        mta_rules, rounding_rules, independent_amount = await self._extract_additional_rules(
            extracted_fields,
            csa_terms,
            provenance
        )
        step5_duration = time.time() - step5_start

        self._add_reasoning_step(
            step_number=5,
            step_name="extract_additional_rules",
            input_data={"fields": ["mta", "rounding", "independent_amount"]},
            output_data={"mta": mta_rules.dict(), "rounding": rounding_rules.dict()},
            reasoning="Extracted MTA, rounding, and independent amount rules from CSA terms",
            model_used="rule-based",
            confidence=0.95,
            duration_seconds=step5_duration
        )

        # Step 6: Calculate complexity score
        complexity_score = self._calculate_complexity_score(
            delivery_pattern,
            threshold_structure,
            haircut_structure
        )

        # Step 7: Identify overall variations
        variations_summary = self._compile_variations_summary(
            delivery_pattern,
            return_pattern,
            threshold_structure,
            haircut_structure
        )

        # Build final result
        processing_time = time.time() - start_time
        overall_confidence = self._get_overall_confidence()

        result = FormulaPatternResult(
            document_id=document_id,
            extraction_timestamp=datetime.utcnow().isoformat(),
            patterns={
                "delivery_amount": delivery_pattern,
                "return_amount": return_pattern
            },
            threshold_structure=threshold_structure,
            haircut_structure=haircut_structure,
            independent_amount=independent_amount,
            mta_rules=mta_rules,
            rounding_rules=rounding_rules,
            complexity_score=complexity_score,
            overall_confidence=overall_confidence,
            agent_reasoning=[step.dict() for step in self.reasoning_chain],
            variations_summary=variations_summary
        )

        return result

    async def _extract_delivery_amount_pattern(
        self,
        extracted_fields: Dict[str, Any],
        column_info: Dict[str, Any],
        csa_terms: CSATerms,
        provenance: Dict[str, Any],
        clauses: Dict[str, Any]
    ) -> FormulaPattern:
        """
        Extract Delivery Amount formula pattern.

        Uses rating column analysis to identify pattern type.
        """
        # Get valuation column names (these hint at rating structure)
        column_names = column_info.get("valuation_column_names", [])
        column_count = column_info.get("valuation_column_count", 0)

        # Get core margin terms for clause text
        core_terms = extracted_fields.get("core_margin_terms", {})

        # Build prompt for LLM analysis
        prompt = f"""Analyze this CSA's Delivery Amount calculation pattern.

RATING COLUMN INFORMATION:
- Number of valuation columns: {column_count}
- Column names: {column_names}

CSA TERMS:
- Party A: {csa_terms.party_a}
- Party B: {csa_terms.party_b}
- Party A Threshold: {csa_terms.party_a_threshold}
- Party B Threshold: {csa_terms.party_b_threshold}

TASK:
Based on the valuation column structure, identify the Delivery Amount calculation pattern.

Pattern Types:
- "greatest_of": Takes the maximum of multiple rating agency calculations (e.g., greatest of Moody's CSA and S&P CSA)
- "sum_of": Sums multiple components together
- "conditional": Different formulas based on trigger events
- "single_rating": Uses only one rating agency
- "other": Custom or non-standard pattern

ANALYSIS RULES:
1. If there are 2+ columns with different agency names (Moody's, S&P, Fitch), it's likely "greatest_of"
2. If columns reference trigger events (First Trigger, Second Trigger), it suggests "conditional" or "greatest_of"
3. If only one column or all columns from same agency, likely "single_rating"
4. Look for keywords: "greatest", "maximum", "higher", "sum", "total"

Return JSON:
{{
    "pattern_type": "greatest_of|sum_of|conditional|single_rating|other",
    "components": ["list of components being aggregated"],
    "confidence": 0.95,
    "reasoning": "Brief explanation of pattern identification",
    "variations_detected": ["list of any unusual elements"]
}}"""

        # Call LLM
        response = await self._call_claude(
            prompt,
            model=self.sonnet_model,
            temperature=0.0,
            max_tokens=2000
        )

        # Parse response
        pattern_type = response.get("pattern_type", "other")
        components = response.get("components", [])
        confidence = response.get("confidence", 0.7)
        reasoning = response.get("reasoning", "")
        variations = response.get("variations_detected", [])

        # Get source page from provenance (check clauses first, then fallback to core_margin_terms)
        source_page = self._get_page_number(provenance, "clauses_to_collect.delivery_amount_clause") or \
                      self._get_page_number(provenance, "core_margin_terms.party_a_threshold")

        # Build clause text from available data (uses actual extracted clauses if available)
        clause_text = self._construct_delivery_clause_text(clauses, column_names)

        return FormulaPattern(
            pattern_name="delivery_amount",
            pattern_type=pattern_type,
            components=components,
            clause_text=clause_text,
            source_page=source_page,
            confidence=confidence,
            variations_detected=variations,
            reasoning=reasoning
        )

    async def _extract_return_amount_pattern(
        self,
        delivery_pattern: FormulaPattern,
        extracted_fields: Dict[str, Any],
        csa_terms: CSATerms,
        provenance: Dict[str, Any],
        clauses: Dict[str, Any]
    ) -> FormulaPattern:
        """
        Extract Return Amount formula pattern.

        Typically mirrors the delivery amount pattern.
        """
        # Return amount usually mirrors delivery amount pattern
        pattern_type = delivery_pattern.pattern_type
        components = delivery_pattern.components.copy()

        # Get actual return amount clause text if available
        return_clauses = clauses.get("return_amount_clause", [])
        if return_clauses and len(return_clauses) > 0:
            clause_text = "\n\n".join(return_clauses)
        else:
            # Fallback to synthesized text if no clauses extracted
            clause_text = f"[Synthesized] The 'Return Amount' calculation typically mirrors the Delivery Amount pattern ({pattern_type})."

        source_page = self._get_page_number(provenance, "clauses_to_collect.return_amount_clause") or \
                      self._get_page_number(provenance, "core_margin_terms.party_b_threshold")

        return FormulaPattern(
            pattern_name="return_amount",
            pattern_type=pattern_type,
            components=components,
            clause_text=clause_text,
            source_page=source_page if source_page > 0 else delivery_pattern.source_page,
            confidence=0.9,  # High confidence as it typically mirrors delivery
            variations_detected=[],
            reasoning="Return Amount pattern inferred from Delivery Amount structure"
        )

    async def _analyze_threshold_structure(
        self,
        extracted_fields: Dict[str, Any],
        csa_terms: CSATerms,
        provenance: Dict[str, Any]
    ) -> ThresholdStructure:
        """
        Analyze threshold structure.

        Identifies if thresholds are fixed, variable by rating, or conditional.
        """
        party_a_threshold = csa_terms.party_a_threshold
        party_b_threshold = csa_terms.party_b_threshold

        # Determine structure type
        structure_type = "fixed"  # Default
        triggers = None

        # Check for rating-based variations
        # If we have multiple rating columns, thresholds might vary by rating
        column_info = extracted_fields.get("column_info", {})
        if column_info.get("valuation_column_count", 0) > 1:
            # Possible variable structure
            structure_type = "variable_by_rating"
            triggers = {
                "rating_agencies": column_info.get("valuation_column_names", []),
                "trigger_events": "Rating-dependent threshold adjustments may apply"
            }

        # Check for asymmetric thresholds
        if party_a_threshold != party_b_threshold:
            if structure_type == "fixed":
                structure_type = "asymmetric"

        # Get source info
        core_terms = extracted_fields.get("core_margin_terms", {})
        source_clause = f"Party A Threshold: {core_terms.get('party_a_threshold', 'N/A')}; Party B Threshold: {core_terms.get('party_b_threshold', 'N/A')}"
        source_page = self._get_page_number(provenance, "core_margin_terms.party_a_threshold")

        return ThresholdStructure(
            structure_type=structure_type,
            party_a_base=party_a_threshold if party_a_threshold != "infinity" else "infinity",
            party_b_base=party_b_threshold if party_b_threshold != float('inf') else "infinity",
            triggers=triggers,
            source_clause=source_clause,
            source_page=source_page,
            confidence=0.95
        )

    async def _analyze_haircut_structure(
        self,
        extracted_fields: Dict[str, Any],
        column_info: Dict[str, Any],
        csa_terms: CSATerms,
        provenance: Dict[str, Any]
    ) -> CollateralHaircutStructure:
        """
        Analyze collateral haircut structure.

        Determines if haircuts are fixed, rating-dependent, or matrix-based.
        """
        column_count = column_info.get("valuation_column_count", 0)
        column_names = column_info.get("valuation_column_names", [])

        # Determine dependency type
        varies_by = []
        dependency_type = "fixed"

        if column_count > 1:
            # Multiple columns suggest rating-dependent or matrix structure
            dependency_type = "rating_dependent"
            varies_by.append("rating_scenario")

        # Check collateral table structure
        eligible_collateral = extracted_fields.get("eligible_collateral_table", [])
        if len(eligible_collateral) > 1:
            varies_by.append("collateral_type")

        if "rating_scenario" in varies_by and "collateral_type" in varies_by:
            dependency_type = "matrix"

        # Get source info (haircut tables are typically in paragraph 11)
        table_reference = "Eligible Collateral Schedule"
        source_page = self._get_page_number(provenance, "eligible_collateral_table")

        if column_count > 1:
            # Build prompt to analyze haircut structure more deeply
            prompt = f"""Analyze the collateral haircut structure for this CSA.

VALUATION COLUMNS: {column_names}
COLLATERAL TYPES: {len(eligible_collateral)} types defined
COLUMN COUNT: {column_count}

Question: How do collateral haircuts vary in this CSA?

Return JSON:
{{
    "dependency_type": "fixed|rating_dependent|matrix|collateral_dependent",
    "rating_scenarios": ["list of rating scenarios if applicable"],
    "confidence": 0.90
}}"""

            response = await self._call_claude(
                prompt,
                model=self.sonnet_model,
                temperature=0.0,
                max_tokens=1500
            )

            dependency_type = response.get("dependency_type", dependency_type)
            rating_scenarios = response.get("rating_scenarios", column_names if column_count > 1 else None)
            confidence = response.get("confidence", 0.85)
        else:
            rating_scenarios = None
            confidence = 0.90

        return CollateralHaircutStructure(
            dependency_type=dependency_type,
            table_reference=table_reference,
            source_page=source_page,
            varies_by=varies_by,
            confidence=confidence,
            rating_scenarios=rating_scenarios
        )

    async def _extract_additional_rules(
        self,
        extracted_fields: Dict[str, Any],
        csa_terms: CSATerms,
        provenance: Dict[str, Any]
    ) -> tuple[MTARules, RoundingRules, Optional[IndependentAmountRules]]:
        """
        Extract MTA, rounding, and independent amount rules.
        """
        core_terms = extracted_fields.get("core_margin_terms", {})

        # MTA Rules
        mta_rules = MTARules(
            party_a_mta=csa_terms.party_a_minimum_transfer_amount,
            party_b_mta=csa_terms.party_b_minimum_transfer_amount,
            structure_type="fixed",  # Can be enhanced to detect variable MTAs
            source_page=self._get_page_number(provenance, "core_margin_terms.party_a_min_transfer_amount")
        )

        # Rounding Rules
        rounding_text = core_terms.get("rounding", "")
        rounding_method = "up" if "up" in rounding_text.lower() else "nearest"
        rounding_increment = csa_terms.rounding if hasattr(csa_terms, 'rounding') else 1000.0

        rounding_rules = RoundingRules(
            rounding_method=rounding_method,
            rounding_increment=rounding_increment,
            applies_to=["delivery_amount"],
            source_page=self._get_page_number(provenance, "core_margin_terms.rounding")
        )

        # Independent Amount Rules
        independent_amount_text = core_terms.get("independent_amount", "Not Applicable")
        has_ia = independent_amount_text.lower() not in ["not applicable", "n/a", "none", ""]

        if has_ia:
            independent_amount = IndependentAmountRules(
                has_independent_amount=True,
                party_a_amount=independent_amount_text,
                party_b_amount=independent_amount_text,
                source_page=self._get_page_number(provenance, "core_margin_terms.independent_amount")
            )
        else:
            independent_amount = IndependentAmountRules(
                has_independent_amount=False,
                party_a_amount=None,
                party_b_amount=None,
                source_page=self._get_page_number(provenance, "core_margin_terms.independent_amount")
            )

        return mta_rules, rounding_rules, independent_amount

    def _calculate_complexity_score(
        self,
        delivery_pattern: FormulaPattern,
        threshold_structure: ThresholdStructure,
        haircut_structure: CollateralHaircutStructure
    ) -> float:
        """
        Calculate overall CSA complexity score.

        Score components:
        - Aggregation pattern complexity (0.0-0.4)
        - Threshold structure complexity (0.0-0.3)
        - Haircut structure complexity (0.0-0.3)
        """
        score = 0.0

        # Aggregation complexity
        if delivery_pattern.pattern_type in ["greatest_of", "sum_of"]:
            component_count = len(delivery_pattern.components)
            score += min(0.2 + (0.1 * (component_count - 1)), 0.4)
        elif delivery_pattern.pattern_type == "conditional":
            score += 0.4

        # Threshold complexity
        if threshold_structure.structure_type == "variable_by_rating":
            score += 0.3
        elif threshold_structure.structure_type == "conditional":
            score += 0.35
        elif threshold_structure.structure_type == "asymmetric":
            score += 0.15

        # Haircut complexity
        if haircut_structure.dependency_type == "rating_dependent":
            score += 0.25
        elif haircut_structure.dependency_type == "matrix":
            score += 0.3

        return min(score, 1.0)

    def _compile_variations_summary(
        self,
        delivery_pattern: FormulaPattern,
        return_pattern: FormulaPattern,
        threshold_structure: ThresholdStructure,
        haircut_structure: CollateralHaircutStructure
    ) -> List[str]:
        """Compile a summary of all variations detected across patterns."""
        variations = []

        variations.extend(delivery_pattern.variations_detected)
        variations.extend(return_pattern.variations_detected)

        if threshold_structure.structure_type not in ["fixed", "asymmetric"]:
            variations.append(f"Non-standard threshold structure: {threshold_structure.structure_type}")

        if haircut_structure.dependency_type == "matrix":
            variations.append("Complex matrix-based haircut structure")

        return list(set(variations))  # Remove duplicates

    def _get_page_number(self, provenance: Dict[str, Any], field_path: str) -> int:
        """Extract page number from provenance data."""
        if not provenance or field_path not in provenance:
            return 0

        field_prov = provenance.get(field_path, {})
        return field_prov.get("page", 0)

    def _construct_delivery_clause_text(
        self,
        clauses: Dict[str, Any],
        column_names: List[str]
    ) -> str:
        """Extract actual delivery amount clause text from ADE extraction."""
        # First try to get actual extracted clause text
        delivery_clauses = clauses.get("delivery_amount_clause", [])

        if delivery_clauses and len(delivery_clauses) > 0:
            # Join multiple clause excerpts with line breaks
            return "\n\n".join(delivery_clauses)

        # Fallback to synthesized text if no clauses extracted
        if not column_names:
            return "[Synthesized] Delivery Amount calculation pattern identified from CSA structure."

        if len(column_names) >= 2:
            agencies = []
            for name in column_names:
                if "moody" in name.lower():
                    agencies.append("Moody's")
                elif "s&p" in name.lower() or "sp" in name.lower():
                    agencies.append("S&P")
                elif "fitch" in name.lower():
                    agencies.append("Fitch")

            agencies = list(set(agencies))  # Remove duplicates

            if len(agencies) >= 2:
                agency_list = " and ".join(agencies[:2])
                return f"[Synthesized] The 'Delivery Amount' will equal the greatest of the {agency_list} Credit Support Amounts."

        return "[Synthesized] Delivery Amount calculated based on eligible collateral valuations."

    # Override normalize method to redirect to extract_patterns
    async def normalize(
        self,
        data: Dict[str, Any],
        document_context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Compatibility wrapper for base class interface.

        For ClauseAgent, use extract_patterns() directly instead.
        """
        # This is a compatibility method - ClauseAgent should use extract_patterns()
        raise NotImplementedError(
            "ClauseAgent uses extract_patterns() instead of normalize(). "
            "Call extract_patterns(document_id, ade_extraction, csa_terms) directly."
        )
