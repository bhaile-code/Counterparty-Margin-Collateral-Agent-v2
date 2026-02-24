"""
Script Generator Agent - Generates annotated Python audit scripts from formula patterns.

This agent takes extracted CSA formula patterns and generates transparent, documented
Python scripts that show the calculation logic with clause citations and pattern annotations.

Purpose:
- Audit-ready documentation
- Transparency into calculation logic
- Educational tool for understanding CSA structures
- Compliance support

Note: Generated scripts are DOCUMENTATION format, not meant for execution.
"""

import ast
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

from app.services.agents.base_agent import BaseNormalizerAgent
from app.models.formula_schemas import FormulaPatternResult
from app.models.schemas import CSATerms, MarginCall
from app.models.agent_schemas import AgentResult

logger = logging.getLogger(__name__)


class ScriptGeneratorAgent(BaseNormalizerAgent):
    """
    Generates annotated Python audit scripts from formula patterns.

    Scripts are NOT meant to be executed - they serve as transparent
    documentation of calculation logic with CSA clause citations.
    """

    def __init__(self, api_key: str):
        """
        Initialize Script Generator Agent.

        Args:
            api_key: Anthropic API key for Claude
        """
        super().__init__(api_key)
        self.agent_name = "ScriptGeneratorAgent"

    async def generate_audit_script(
        self,
        formula_patterns: FormulaPatternResult,
        csa_terms: CSATerms,
        margin_call: Optional[MarginCall] = None,
        document_id: Optional[str] = None
    ) -> str:
        """
        Generate annotated Python script showing calculation logic.

        Args:
            formula_patterns: Extracted formula patterns from Clause Agent
            csa_terms: Normalized CSA terms
            margin_call: Optional margin call result for sample values
            document_id: Optional document ID for script header

        Returns:
            Python code as string (not executable - documentation format)

        Raises:
            ValueError: If generated script has syntax errors
        """
        start_time = time.time()
        self._clear_reasoning_chain()

        # Step 1: Build comprehensive prompt
        prompt = self._build_generation_prompt(
            formula_patterns,
            csa_terms,
            margin_call,
            document_id
        )

        self._add_reasoning_step(
            step_number=1,
            step_name="build_prompt",
            input_data={
                "pattern_type": formula_patterns.patterns.get("delivery_amount", {}).pattern_type if "delivery_amount" in formula_patterns.patterns else "unknown",
                "complexity_score": formula_patterns.complexity_score,
                "has_margin_call": margin_call is not None
            },
            output_data={"prompt_length": len(prompt)},
            reasoning="Built comprehensive prompt with pattern context for script generation",
            model_used="rule-based"
        )

        # Step 2: Call LLM to generate script
        step_2_start = time.time()
        response = await self._call_claude(
            prompt=prompt,
            model=self.sonnet_model,
            temperature=0.3,  # Some creativity but mostly deterministic
            max_tokens=8000  # Increased to allow longer script generation
        )
        step_2_duration = time.time() - step_2_start

        self._add_reasoning_step(
            step_number=2,
            step_name="generate_script",
            input_data={"model": self.sonnet_model, "temperature": 0.3},
            output_data={"response_type": "code"},
            reasoning="Generated audit script using Claude Sonnet 4.5",
            model_used="sonnet",
            duration_seconds=step_2_duration,
            confidence=0.9
        )

        # Step 3: Extract code from response
        script = self._extract_code(response)

        self._add_reasoning_step(
            step_number=3,
            step_name="extract_code",
            input_data={"raw_response_length": len(str(response))},
            output_data={"script_length": len(script), "lines": len(script.split('\n'))},
            reasoning="Extracted Python code from LLM response",
            model_used="rule-based"
        )

        # Step 4: Validate syntax
        is_valid, error_message = self._validate_syntax(script)

        if not is_valid:
            logger.error(f"Generated script has syntax errors: {error_message}")

            self._add_reasoning_step(
                step_number=4,
                step_name="validate_syntax",
                input_data={"script_preview": script[:200]},
                output_data={"valid": False, "error": error_message},
                reasoning=f"Syntax validation failed: {error_message}",
                model_used="rule-based",
                confidence=0.0
            )

            raise ValueError(f"Generated script has syntax errors: {error_message}")

        self._add_reasoning_step(
            step_number=4,
            step_name="validate_syntax",
            input_data={"script_length": len(script)},
            output_data={"valid": True},
            reasoning="Script passed AST syntax validation",
            model_used="rule-based",
            confidence=1.0
        )

        # Step 5: Enhance with additional annotations (if needed)
        enhanced_script = self._enhance_with_annotations(script, formula_patterns)

        total_time = time.time() - start_time

        self._add_reasoning_step(
            step_number=5,
            step_name="finalize",
            input_data={"original_length": len(script)},
            output_data={"final_length": len(enhanced_script)},
            reasoning=f"Finalized script generation in {total_time:.2f}s",
            model_used="rule-based",
            duration_seconds=total_time
        )

        logger.info(
            f"Successfully generated audit script: {len(enhanced_script)} chars, "
            f"{len(enhanced_script.split(chr(10)))} lines in {total_time:.2f}s"
        )

        return enhanced_script

    def _build_generation_prompt(
        self,
        patterns: FormulaPatternResult,
        csa_terms: CSATerms,
        margin_call: Optional[MarginCall],
        document_id: Optional[str]
    ) -> str:
        """
        Build comprehensive prompt for script generation.

        Args:
            patterns: Formula pattern extraction result
            csa_terms: Normalized CSA terms
            margin_call: Optional margin call for sample values
            document_id: Optional document ID

        Returns:
            Formatted prompt for Claude
        """
        # Get delivery pattern info
        delivery_pattern = patterns.patterns.get("delivery_amount")
        delivery_type = delivery_pattern.pattern_type if delivery_pattern else "unknown"
        delivery_components = delivery_pattern.components if delivery_pattern else []

        # Get threshold info
        threshold_type = patterns.threshold_structure.structure_type
        has_triggers = patterns.threshold_structure.triggers is not None

        # Get haircut info
        haircut_type = patterns.haircut_structure.dependency_type
        varies_by = patterns.haircut_structure.varies_by

        # Build margin call summary if available
        margin_summary = ""
        if margin_call:
            margin_summary = f"""
# Sample Calculation Result:
Net Exposure: {margin_call.net_exposure}
Effective Collateral: {margin_call.effective_collateral}
Threshold: {margin_call.threshold}
Exposure Above Threshold: {margin_call.exposure_above_threshold}
Action: {margin_call.action}
Amount: {margin_call.amount}
"""

        prompt = f"""You are generating a transparent audit calculation script for a CSA margin calculation.

This script is DOCUMENTATION - not meant to execute. Its purpose is to show:
1. Step-by-step calculation logic
2. CSA clause citations with page numbers
3. Where this CSA's specific patterns appear
4. How other CSAs might differ
5. Pattern-aware annotations

# Document Information:
Document ID: {document_id or 'Unknown'}
CSA Type: {patterns.get_csa_type_label()}
Complexity Score: {patterns.complexity_score:.2f} ({patterns.get_csa_type_label()})
Generation Date: {datetime.utcnow().isoformat()}

# CSA Parties:
Party A: {csa_terms.party_a}
Party B: {csa_terms.party_b}

# Threshold Structure:
Type: {threshold_type}
Party A Threshold: {csa_terms.party_a_threshold}
Party B Threshold: {csa_terms.party_b_threshold}
Rating Triggers: {"Yes" if has_triggers else "No"}

# MTA Rules:
Party A MTA: {csa_terms.party_a_minimum_transfer_amount}
Party B MTA: {csa_terms.party_b_minimum_transfer_amount}
Rounding: {csa_terms.rounding}

# Delivery Amount Pattern:
Pattern Type: {delivery_type}
Components: {', '.join(delivery_components) if delivery_components else 'None'}
Source Page: {delivery_pattern.source_page if delivery_pattern else 'Unknown'}
Confidence: {delivery_pattern.confidence if delivery_pattern else 0.0:.0%}

# Haircut Structure:
Dependency Type: {haircut_type}
Varies By: {', '.join(varies_by)}
{margin_summary}

# TASK:
Generate a well-documented Python script with the following structure:

## 1. HEADER COMMENT BLOCK
Include:
- Document ID, parties, generation date
- CSA type and pattern summary
- Key characteristics (complexity, pattern type)
- Disclaimer that this is documentation format

## 2. CONSTANTS SECTION
Define:
- Party names
- Threshold values
- MTA values
- Rounding amount
- Haircut tables (as nested dicts if rating-dependent)
- Any other fixed values

## 3. MAIN CALCULATION FUNCTION
Function signature: calculate_margin_requirement(net_exposure, posted_collateral, rating_scenario)

Include:
- Step-by-step calculation matching the pattern type
- Inline comments citing CSA clauses with page numbers
- Pattern annotations (e.g., "# This CSA uses greatest-of pattern - see Page 5")
- Variation notes (e.g., "# NOTE: Other CSAs might use sum-of instead")
- Clear variable names
- Calculation steps for: delivery_amount, return_amount, margin_required

## 4. HELPER FUNCTIONS
Implement as needed:
- get_haircut(rating_scenario, collateral_type) - pattern-specific logic
- get_threshold(party, rating_scenario) - handle fixed vs variable
- apply_mta(amount, mta) - minimum transfer amount logic
- apply_rounding(amount, rounding) - rounding logic
- calculate_csa_component(exposure, threshold, haircut) - CSA calculation

## 5. PATTERN-SPECIFIC LOGIC
For {delivery_type} pattern:
{self._get_pattern_specific_guidance(delivery_type, delivery_components)}

## 6. BOTTOM SUMMARY COMMENT
Include:
- List of all patterns used in this CSA
- Notes on how this differs from "standard" CSAs
- Complexity assessment reasoning
- References to key CSA sections

# REQUIREMENTS:
1. MUST be valid Python syntax (will be validated with ast.parse)
2. Use clear, readable code with meaningful variable names
3. Include extensive inline documentation
4. Cite CSA clauses and page numbers in comments
5. Add pattern-aware annotations explaining WHY this approach is used
6. Note variations from typical CSA patterns
7. Use type hints for function signatures
8. Follow PEP 8 style guidelines
9. Make it educational - explain the logic, don't just implement it

# OUTPUT:
Return ONLY the Python code, no explanations before or after.
Start with triple-quoted docstring, end with summary comment.
"""

        return prompt

    def _get_pattern_specific_guidance(self, pattern_type: str, components: list) -> str:
        """
        Get pattern-specific generation guidance.

        Args:
            pattern_type: Type of pattern (greatest_of, sum_of, etc.)
            components: List of components

        Returns:
            Specific guidance text
        """
        guidance_map = {
            "greatest_of": f"""
- Calculate each component separately: {', '.join(components)}
- Take the MAXIMUM of all components
- Add comment explaining dual-agency maximum logic
- Note that other CSAs might use single agency or sum-of
""",
            "sum_of": f"""
- Calculate each component separately: {', '.join(components)}
- SUM all components together
- Add comment explaining additive aggregation
- Note that other CSAs might use greatest-of
""",
            "single_rating": """
- Calculate CSA based on single rating agency
- Simpler logic than dual-agency
- Note that other CSAs might use multiple agencies
""",
            "conditional": """
- Implement conditional logic based on triggers
- Use if/elif/else for different scenarios
- Document trigger conditions
- Note complexity compared to simple patterns
""",
            "other": """
- Implement custom logic based on pattern details
- Document any unusual or non-standard elements
- Explain why this pattern is different
"""
        }

        return guidance_map.get(pattern_type, guidance_map["other"])

    def _extract_code(self, response: Dict[str, Any]) -> str:
        """
        Extract Python code from LLM response.

        Handles responses that may:
        - Be plain text (already code)
        - Contain markdown code blocks
        - Have JSON wrapper

        Args:
            response: LLM response (dict or string)

        Returns:
            Extracted Python code
        """
        # Handle dict response (from _call_claude)
        if isinstance(response, dict):
            if "raw_text" in response:
                code = response["raw_text"]
            else:
                # Try to find any string value
                code = str(response)
        else:
            code = str(response)

        # Remove markdown code blocks if present
        if "```python" in code:
            parts = code.split("```python")
            if len(parts) > 1:
                code = parts[1].split("```")[0]
        elif "```" in code:
            parts = code.split("```")
            if len(parts) >= 3:
                code = parts[1]

        return code.strip()

    def _validate_syntax(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate Python syntax using AST.

        Args:
            code: Python code to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            error_msg = f"Line {e.lineno}: {e.msg}"
            logger.error(f"Syntax error in generated script: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(f"Unexpected error validating script: {error_msg}")
            return False, error_msg

    def _enhance_with_annotations(
        self,
        script: str,
        patterns: FormulaPatternResult
    ) -> str:
        """
        Enhance script with additional pattern annotations if needed.

        This is a hook for future enhancements. Currently returns script as-is
        since LLM should generate comprehensive annotations.

        Args:
            script: Generated Python script
            patterns: Formula patterns

        Returns:
            Enhanced script
        """
        # Future: Could add additional metadata comments, version info, etc.
        # For now, trust LLM to generate comprehensive annotations
        return script

    async def normalize(
        self,
        data: Dict[str, Any],
        document_context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Normalize method - not used by Script Generator.

        Script Generator uses generate_audit_script() directly.
        This method exists to satisfy BaseNormalizerAgent interface.

        Args:
            data: Not used
            document_context: Not used

        Returns:
            AgentResult with error
        """
        return self._format_result(
            data={"error": "Use generate_audit_script() method instead"},
            processing_time=0.0,
            confidence=0.0
        )
