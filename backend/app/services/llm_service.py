"""
LLM-Powered Explanation Generation Service.

This service uses Claude API to generate human-readable explanations
of margin calculations with citations to specific CSA contract clauses.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from app.config import settings
from app.models.schemas import (
    CSATerms,
    MarginCall,
    CalculationStep,
    MarginCallAction,
)
from app.models.formula_schemas import FormulaPatternResult

logger = logging.getLogger(__name__)


class ExplanationGeneratorService:
    """Service for generating LLM-powered explanations of margin calculations."""

    def __init__(self, anthropic_client: Optional[Anthropic] = None):
        """
        Initialize the explanation service.

        Args:
            anthropic_client: Optional Anthropic client. If not provided,
                            creates one using settings.anthropic_api_key
        """
        self.client = anthropic_client or Anthropic(api_key=settings.anthropic_api_key)
        self.model = (
            "claude-sonnet-4-5-20250929"  # Sonnet 4.5 for high-quality explanations
        )

    def generate_explanation(
        self,
        margin_call: MarginCall,
        csa_terms: CSATerms,
        document_id: str,
        formula_patterns: Optional[FormulaPatternResult] = None,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive explanation of a margin calculation.

        Args:
            margin_call: The calculated margin call result
            csa_terms: The CSA terms that govern this calculation
            document_id: Source document ID for provenance
            formula_patterns: Optional formula patterns extracted from CSA document
                            (enhances explanation with pattern context)

        Returns:
            Dictionary containing:
                - narrative: Human-readable explanation with citations
                - calculation_breakdown: Step-by-step analysis
                - key_factors: List of key factors
                - audit_trail: Chronological event log
                - citations: Mapping of clauses to page numbers
                - generated_at: Timestamp
                - model_used: Model name
                - pattern_analysis: Optional pattern analysis if patterns provided

        Raises:
            ValueError: If input data is invalid
            Exception: If generation fails
        """
        pattern_enhanced = formula_patterns is not None
        logger.info(
            f"Generating explanation for margin call on document {document_id} "
            f"(pattern-enhanced: {pattern_enhanced})"
        )

        # Validate inputs
        if not margin_call.calculation_steps:
            raise ValueError("Margin call must include calculation steps")

        try:
            # Build the prompt
            prompt = self._build_explanation_prompt(
                margin_call=margin_call,
                csa_terms=csa_terms,
                formula_patterns=formula_patterns
            )

            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,  # Balanced for natural but consistent narratives
                system=self._get_system_prompt(),
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            response_text = response.content[0].text

            # Try to extract JSON from response
            explanation_data = self._parse_response(response_text)

            # Add metadata
            explanation_data["generated_at"] = datetime.utcnow().isoformat()
            explanation_data["llm_model"] = self.model
            explanation_data["document_id"] = document_id
            explanation_data["margin_call_action"] = margin_call.action.value
            explanation_data["margin_call_amount"] = margin_call.amount
            explanation_data["counterparty_name"] = margin_call.counterparty_name or csa_terms.party_a or "Unknown"

            # Add pattern analysis if formula patterns were provided
            if formula_patterns:
                explanation_data["pattern_analysis"] = {
                    "csa_type": formula_patterns.get_csa_type_label(),
                    "complexity_score": formula_patterns.complexity_score,
                    "complexity_factors": formula_patterns.assess_complexity_factors(),
                    "variations_from_standard": formula_patterns.variations_summary
                }
            else:
                explanation_data["pattern_analysis"] = None

            logger.info(
                f"Successfully generated explanation for {margin_call.counterparty_name or 'Unknown'} "
                f"(pattern-enhanced: {pattern_enhanced})"
            )

            return explanation_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {str(e)}")
            raise ValueError(f"Invalid response format from LLM: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}", exc_info=True)
            raise

    def _get_system_prompt(self) -> str:
        """Get the system prompt for Claude."""
        return """You are a financial expert specializing in OTC derivatives collateral management and ISDA Credit Support Annex (CSA) agreements.

Your task is to generate clear, professional explanations of margin call calculations that:
1. Explain WHY a margin call was made (or not made)
2. Reference specific CSA clauses that govern each calculation step
3. Provide citations to source document sections and page numbers
4. Create an audit trail showing the decision flow
5. Use clear, professional language suitable for operations teams

Your explanations should:
- Be factual and based only on the provided data
- Cite specific CSA clauses (e.g., "Section 3(a)" or "Paragraph 13")
- Link calculations to contractual requirements
- Explain technical terms when first used
- Be structured and easy to follow

You must respond with ONLY valid JSON in the specified format, no other text."""

    def _build_explanation_prompt(
        self,
        margin_call: MarginCall,
        csa_terms: CSATerms,
        formula_patterns: Optional[FormulaPatternResult] = None
    ) -> str:
        """Build the user prompt for explanation generation."""

        # Format calculation steps
        steps_text = []
        for step in margin_call.calculation_steps:
            step_info = f"**Step {step.step_number}: {step.description}**\n"
            if step.formula:
                step_info += f"  Formula: {step.formula}\n"
            step_info += f"  Inputs: {json.dumps(step.inputs, indent=4)}\n"
            step_info += f"  Result: ${step.result:,.2f}\n"
            if step.source_clause:
                step_info += f"  CSA Clause: {step.source_clause}\n"
            steps_text.append(step_info)

        # Format collateral details
        collateral_text = []
        for item in margin_call.posted_collateral_items:
            collateral_text.append(
                f"- {item.collateral_type.value}: Market Value ${item.market_value:,.2f}, "
                f"Haircut {item.haircut_rate * 100:.1f}%, "
                f"Effective Value ${item.effective_value:,.2f}"
            )

        # Format CSA terms
        csa_text = f"""**CSA Terms Summary**
- Party A: {csa_terms.party_a or 'Unknown'}
- Party B: {csa_terms.party_b or 'Unknown'}
- Counterparty (from calculation): {margin_call.counterparty_name or 'Unknown'}
- Party A Threshold: ${csa_terms.party_a_threshold:,.2f}
- Party B Threshold: ${csa_terms.party_b_threshold:,.2f}
- Party A Minimum Transfer Amount (MTA): ${csa_terms.party_a_minimum_transfer_amount:,.2f}
- Party B Minimum Transfer Amount (MTA): ${csa_terms.party_b_minimum_transfer_amount:,.2f}
- Party A Independent Amount: ${csa_terms.party_a_independent_amount or 0:,.2f}
- Party B Independent Amount: ${csa_terms.party_b_independent_amount or 0:,.2f}
- Rounding Increment: ${csa_terms.rounding:,.2f}
- Currency: {csa_terms.currency.value}
"""

        # Add source page information if available
        if csa_terms.source_pages:
            csa_text += f"\n**Source Document References:**\n"
            for field, page_info in csa_terms.source_pages.items():
                if isinstance(page_info, dict):
                    page_num = page_info.get("page", "unknown")
                else:
                    page_num = page_info
                csa_text += f"- {field}: Page {page_num}\n"

        # Build formula pattern context (if available)
        pattern_context = ""
        if formula_patterns:
            pattern_context = self._build_pattern_context(formula_patterns)

        prompt = f"""Generate a comprehensive explanation for the following margin call calculation:

# Margin Call Result
- Action: {margin_call.action.value}
- Amount: ${margin_call.amount:,.2f}
- Currency: {margin_call.currency.value}
- Calculation Date: {margin_call.calculation_date.strftime('%Y-%m-%d %H:%M:%S UTC')}

# Key Figures
- Net Exposure: ${margin_call.net_exposure:,.2f}
- Threshold: ${margin_call.threshold:,.2f}
- Posted Collateral (Market Value): ${sum(item.market_value for item in margin_call.posted_collateral_items):,.2f}
- Effective Collateral (After Haircuts): ${margin_call.effective_collateral:,.2f}
- Exposure Above Threshold: ${margin_call.exposure_above_threshold:,.2f}

# Posted Collateral Details
{chr(10).join(collateral_text) if collateral_text else "No collateral posted"}

{csa_text}

{pattern_context}

# Calculation Steps
{chr(10).join(steps_text)}

---

Return a JSON object with this exact structure:
{{
  "narrative": "A comprehensive 3-5 paragraph explanation in professional language. Start with an executive summary, then explain the calculation step-by-step, and conclude with the outcome. IMPORTANT CITATION RULES: (1) If actual CSA clause text is provided in the Formula Pattern Analysis section above, quote it verbatim. (2) Do NOT create generic references like 'per Paragraph 13' or 'Section 3(a)' unless the actual clause text has been provided. (3) If no actual clause text is available, omit clause citations entirely and focus on explaining the calculation logic.",

  "key_factors": [
    "List 3-5 key factors that drove this calculation result",
    "Each should be a concise statement",
    "Focus on material impacts (threshold comparison, MTA filter, haircuts, etc.)"
  ],

  "calculation_breakdown": [
    {{
      "step_number": 1,
      "step_name": "Brief name of this step",
      "explanation": "Clear explanation of what this step does and why. If actual CSA clause text was provided above, quote it here. Otherwise, explain the logic without fabricating clause references.",
      "csa_clause_reference": null (do NOT create generic references - only include actual quoted text or use null),
      "source_page": 5 or null,
      "calculation": "Formula with actual values",
      "result": "Result with interpretation"
    }}
  ],

  "audit_trail": [
    {{
      "timestamp": "ISO 8601 timestamp (use calculation date as base)",
      "event": "Event description",
      "details": "Additional context - do NOT fabricate clause references here either"
    }}
  ],

  "citations": {{
    "Only include entries if actual CSA clause text was provided above": "page number or null"
  }},

  "risk_assessment": "Brief assessment of the collateral position and any potential risks or observations",

  "next_steps": "What should operations do next (e.g., 'Issue margin call notice to counterparty', 'No action required', etc.)"
}}

CRITICAL INSTRUCTIONS:
- Use ONLY information provided above - NEVER make up clause numbers, paragraph references, or section citations
- If actual CSA clause text is provided in the Formula Pattern Analysis section, quote it verbatim in your explanation
- If NO actual clause text is provided, do NOT create generic references like "per Paragraph 13 [Page 4]" or "Section 3(a)"
- Better to have no clause citations than fabricated ones
- If source page information is not available for a field, use null for source_page
- Ensure all dollar amounts match the provided calculation
- The narrative should be suitable for sending to operations teams or counterparties
- Explain WHY the action was taken (or not taken), not just WHAT happened
"""

        return prompt

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the LLM response, handling potential markdown code blocks.

        Args:
            response_text: Raw response from Claude

        Returns:
            Parsed JSON data

        Raises:
            json.JSONDecodeError: If response is not valid JSON
        """
        # Remove potential markdown code blocks
        text = response_text.strip()

        # Check for markdown JSON code block
        if text.startswith("```json"):
            text = text[7:]  # Remove ```json
        elif text.startswith("```"):
            text = text[3:]  # Remove ```

        if text.endswith("```"):
            text = text[:-3]  # Remove closing ```

        text = text.strip()

        # Parse JSON
        return json.loads(text)

    def _build_pattern_context(self, formula_patterns: FormulaPatternResult) -> str:
        """
        Build formula pattern context section for the prompt.

        This adds information about the CSA's calculation patterns to help
        the LLM explain WHY specific calculation methods are used.

        Args:
            formula_patterns: Extracted formula patterns

        Returns:
            Formatted pattern context string
        """
        context = "# Formula Pattern Analysis\n\n"
        context += f"**CSA Type:** {formula_patterns.get_csa_type_label()}\n"
        context += f"**Complexity Score:** {formula_patterns.complexity_score:.2f} "
        context += f"({formula_patterns.assess_complexity_factors()['overall_assessment']})\n\n"

        # Delivery amount pattern with actual clause text
        if "delivery_amount" in formula_patterns.patterns:
            delivery = formula_patterns.patterns["delivery_amount"]
            context += f"**Delivery Amount Pattern:**\n"
            context += f"- Pattern Type: {delivery.pattern_type.replace('_', ' ').title()}\n"
            if delivery.components:
                context += f"- Components: {', '.join(delivery.components)}\n"
            context += f"- Source: Page {delivery.source_page}\n"

            # Include actual clause text if available
            if delivery.clause_text and not delivery.clause_text.startswith("[Synthesized]"):
                context += f"\n**Actual CSA Clause Text (Delivery Amount):**\n"
                context += f'"{delivery.clause_text}"\n'
                context += f"(Source: Page {delivery.source_page})\n\n"

            if delivery.variations_detected:
                context += f"- Variations: {', '.join(delivery.variations_detected)}\n"
            context += f"- Confidence: {delivery.confidence:.0%}\n\n"

        # Return amount pattern with actual clause text
        if "return_amount" in formula_patterns.patterns:
            return_amount = formula_patterns.patterns["return_amount"]
            if return_amount.clause_text and not return_amount.clause_text.startswith("[Synthesized]"):
                context += f"**Actual CSA Clause Text (Return Amount):**\n"
                context += f'"{return_amount.clause_text}"\n'
                context += f"(Source: Page {return_amount.source_page})\n\n"

        # Threshold structure with actual clause text
        context += f"**Threshold Structure:**\n"
        context += f"- Type: {formula_patterns.threshold_structure.structure_type.replace('_', ' ').title()}\n"
        context += f"- Party A Threshold: {formula_patterns.threshold_structure.party_a_base}\n"
        context += f"- Party B Threshold: {formula_patterns.threshold_structure.party_b_base}\n"
        if formula_patterns.threshold_structure.triggers:
            context += f"- Has Rating Triggers: Yes\n"
        context += f"- Source: Page {formula_patterns.threshold_structure.source_page}\n"

        # Include actual threshold clause text if available
        if hasattr(formula_patterns.threshold_structure, 'source_clause') and formula_patterns.threshold_structure.source_clause:
            if not formula_patterns.threshold_structure.source_clause.startswith("[Synthesized]"):
                context += f"\n**Actual CSA Clause Text (Threshold):**\n"
                context += f'"{formula_patterns.threshold_structure.source_clause}"\n'
                context += f"(Source: Page {formula_patterns.threshold_structure.source_page})\n"
        context += "\n"

        # Haircut structure
        context += f"**Haircut Structure:**\n"
        context += f"- Dependency Type: {formula_patterns.haircut_structure.dependency_type.replace('_', ' ').title()}\n"
        if formula_patterns.haircut_structure.varies_by:
            context += f"- Varies By: {', '.join(formula_patterns.haircut_structure.varies_by)}\n"
        if formula_patterns.haircut_structure.rating_scenarios:
            context += f"- Rating Scenarios: {len(formula_patterns.haircut_structure.rating_scenarios)} scenarios\n"
        context += f"- Source: Page {formula_patterns.haircut_structure.source_page}\n\n"

        # Pattern guidance
        context += "**Explanation Guidance:**\n"
        context += "When generating your explanation, please:\n"
        context += f"1. Explain WHY this CSA uses a {formula_patterns.patterns['delivery_amount'].pattern_type.replace('_', ' ')} pattern (if applicable)\n"
        context += "2. Note how this pattern affects the specific calculation steps\n"
        context += "3. Mention how other CSAs might differ (e.g., single rating vs dual rating agency)\n"
        context += "4. IMPORTANT: If actual CSA clause text is provided above, quote it directly in your explanation\n"
        context += "5. IMPORTANT: Do NOT make up generic clause references like 'Paragraph 13' or 'Section 3(a)'\n"
        context += "6. IMPORTANT: If no actual clause text is available, do NOT include clause citations at all\n\n"

        return context


# Global service instance
explanation_generator_service = ExplanationGeneratorService()
