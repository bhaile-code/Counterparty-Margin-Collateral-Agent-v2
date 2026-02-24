"""
Unit tests for Script Generator Agent.

Tests cover:
- Script generation with valid patterns
- Syntax validation
- Prompt building
- Code extraction
- Error handling
"""

import pytest
import ast
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.agents.script_generator_agent import ScriptGeneratorAgent
from app.models.formula_schemas import (
    FormulaPatternResult,
    FormulaPattern,
    ThresholdStructure,
    CollateralHaircutStructure,
)
from app.models.schemas import CSATerms, MarginCall


@pytest.fixture
def mock_api_key():
    """Mock API key for testing."""
    return "test_api_key"


@pytest.fixture
def sample_formula_patterns():
    """Sample formula patterns for testing."""
    return FormulaPatternResult(
        document_id="test_doc_123",
        extraction_timestamp="2025-11-09T12:00:00Z",
        patterns={
            "delivery_amount": FormulaPattern(
                pattern_name="delivery_amount",
                pattern_type="greatest_of",
                components=["moodys_csa", "sp_csa"],
                clause_text="The 'Delivery Amount' will equal the greatest of the Moody's Credit Support Amount and the S&P Credit Support Amount",
                source_page=5,
                confidence=0.95,
                variations_detected=[],
            )
        },
        threshold_structure=ThresholdStructure(
            structure_type="fixed",
            party_a_base="INFINITY",
            party_b_base=0,
            triggers=None,
            source_clause="Threshold amounts are fixed as specified",
            source_page=6,
        ),
        haircut_structure=CollateralHaircutStructure(
            dependency_type="rating_dependent",
            table_reference="Paragraph 11(e)(ii)",
            source_page=7,
            varies_by=["rating_scenario", "collateral_type"],
            rating_scenarios=["AA_AA", "AA_A", "A_A", "BBB_BBB"],
        ),
        independent_amount=None,
        mta_rules={},
        rounding_rules={},
        complexity_score=0.45,
        overall_confidence=0.92,
    )


@pytest.fixture
def sample_csa_terms():
    """Sample CSA terms for testing."""
    return CSATerms(
        document_id="test_doc_123",
        party_a_name="Bank XYZ",
        party_b_name="Hedge Fund ABC",
        party_a_threshold="INFINITY",
        party_b_threshold=0,
        party_a_mta=500000,
        party_b_mta=500000,
        rounding_amount=100000,
        base_currency="USD",
        eligible_collateral=[],
        collateral_table=None,
    )


@pytest.fixture
def sample_margin_call():
    """Sample margin call for testing."""
    return MarginCall(
        calculation_id="calc_123",
        document_id="test_doc_123",
        net_exposure=10000000,
        posted_collateral=5000000,
        delivery_amount=12000000,
        return_amount=0,
        margin_required=7000000,
        margin_call_direction="deliver",
        currency="USD",
        calculated_at="2025-11-09T12:00:00Z",
        calculation_steps=[],
        counterparty_name="Hedge Fund ABC",
    )


@pytest.fixture
def script_generator_agent(mock_api_key):
    """Create Script Generator Agent instance."""
    return ScriptGeneratorAgent(api_key=mock_api_key)


# Test: Script Generation
class TestScriptGeneration:
    """Tests for script generation functionality."""

    @pytest.mark.asyncio
    async def test_generate_script_greatest_of_pattern(
        self, script_generator_agent, sample_formula_patterns, sample_csa_terms, sample_margin_call
    ):
        """Test script generation with greatest_of pattern."""
        # Mock the Claude API call
        valid_python_script = '''"""
CSA AUDIT SCRIPT - test_doc_123
Generated: 2025-11-09
Parties: Bank XYZ vs Hedge Fund ABC
"""

def calculate_margin_requirement(net_exposure, posted_collateral, rating_scenario):
    """Calculate margin requirement using greatest-of pattern."""
    # DELIVERY AMOUNT CALCULATION (Page 5)
    moodys_csa = max(net_exposure - 0, 0)  # Simplified
    sp_csa = max(net_exposure - 0, 0)  # Simplified

    # Greatest-of aggregation
    delivery_amount = max(moodys_csa, sp_csa)

    return delivery_amount
'''

        script_generator_agent._call_claude = AsyncMock(
            return_value={"raw_text": valid_python_script}
        )

        # Generate script
        result = await script_generator_agent.generate_audit_script(
            formula_patterns=sample_formula_patterns,
            csa_terms=sample_csa_terms,
            margin_call=sample_margin_call,
            document_id="test_doc_123",
        )

        # Assertions
        assert isinstance(result, str)
        assert len(result) > 0
        assert "def calculate_margin_requirement" in result
        assert "greatest-of" in result.lower()
        assert "test_doc_123" in result

        # Verify reasoning chain
        assert len(script_generator_agent.reasoning_chain) > 0
        step_names = [step.step_name for step in script_generator_agent.reasoning_chain]
        assert "build_prompt" in step_names
        assert "generate_script" in step_names
        assert "validate_syntax" in step_names

    @pytest.mark.asyncio
    async def test_generate_script_single_rating_pattern(
        self, script_generator_agent, sample_formula_patterns, sample_csa_terms
    ):
        """Test script generation with single rating pattern."""
        # Modify pattern to single rating
        sample_formula_patterns.patterns["delivery_amount"].pattern_type = "single_rating"
        sample_formula_patterns.patterns["delivery_amount"].components = ["sp_csa"]

        valid_python_script = '''"""CSA AUDIT SCRIPT"""
def calculate_margin_requirement(net_exposure, posted_collateral, rating_scenario):
    """Single rating agency calculation."""
    sp_csa = net_exposure
    return sp_csa
'''

        script_generator_agent._call_claude = AsyncMock(
            return_value={"raw_text": valid_python_script}
        )

        # Generate script
        result = await script_generator_agent.generate_audit_script(
            formula_patterns=sample_formula_patterns,
            csa_terms=sample_csa_terms,
            document_id="test_doc_123",
        )

        # Assertions
        assert isinstance(result, str)
        assert "single rating" in result.lower() or "sp_csa" in result

    @pytest.mark.asyncio
    async def test_generate_script_complex_csa(
        self, script_generator_agent, sample_formula_patterns, sample_csa_terms
    ):
        """Test script generation for complex CSA."""
        # Increase complexity
        sample_formula_patterns.complexity_score = 0.85
        sample_formula_patterns.threshold_structure.structure_type = "variable_by_rating"
        sample_formula_patterns.threshold_structure.triggers = {"AA": 1000000, "A": 500000}

        valid_python_script = '''"""Complex CSA"""
def calculate_margin_requirement(net_exposure, posted_collateral, rating_scenario):
    """Complex calculation with triggers."""
    threshold = get_threshold(rating_scenario)
    delivery_amount = max(net_exposure - threshold, 0)
    return delivery_amount

def get_threshold(rating_scenario):
    """Get rating-dependent threshold."""
    if rating_scenario == "AA":
        return 1000000
    return 500000
'''

        script_generator_agent._call_claude = AsyncMock(
            return_value={"raw_text": valid_python_script}
        )

        # Generate script
        result = await script_generator_agent.generate_audit_script(
            formula_patterns=sample_formula_patterns,
            csa_terms=sample_csa_terms,
        )

        # Assertions
        assert "get_threshold" in result
        assert "rating_scenario" in result


# Test: Syntax Validation
class TestSyntaxValidation:
    """Tests for Python syntax validation."""

    def test_validate_valid_python(self, script_generator_agent):
        """Test validation of valid Python code."""
        valid_code = """
def hello_world():
    print("Hello, World!")
    return 42
"""
        is_valid, error = script_generator_agent._validate_syntax(valid_code)

        assert is_valid is True
        assert error is None

    def test_validate_invalid_python(self, script_generator_agent):
        """Test validation of invalid Python code."""
        invalid_code = """
def hello_world():
    print("Hello, World!"
    return 42  # Missing closing parenthesis above
"""
        is_valid, error = script_generator_agent._validate_syntax(invalid_code)

        assert is_valid is False
        assert error is not None
        assert isinstance(error, str)

    def test_validate_syntax_error_details(self, script_generator_agent):
        """Test that syntax error provides line number."""
        invalid_code = """
def foo():
    x = 1
    y = 2 +  # Incomplete expression
    return x + y
"""
        is_valid, error = script_generator_agent._validate_syntax(invalid_code)

        assert is_valid is False
        assert "Line" in error or "line" in error.lower()

    def test_extract_code_from_markdown(self, script_generator_agent):
        """Test extracting code from markdown blocks."""
        markdown_response = """
Here's the script:

```python
def test():
    return "extracted"
```

Some text after.
"""
        extracted = script_generator_agent._extract_code(markdown_response)

        assert "def test():" in extracted
        assert "return \"extracted\"" in extracted
        assert "Some text after" not in extracted

    def test_extract_code_plain_text(self, script_generator_agent):
        """Test extracting code from plain text."""
        plain_code = 'def test():\n    return "plain"'
        extracted = script_generator_agent._extract_code(plain_code)

        assert extracted == plain_code

    def test_extract_code_from_dict(self, script_generator_agent):
        """Test extracting code from dict response."""
        dict_response = {"raw_text": "def test():\n    return 1"}
        extracted = script_generator_agent._extract_code(dict_response)

        assert "def test():" in extracted


# Test: Prompt Building
class TestPromptBuilding:
    """Tests for prompt construction."""

    def test_build_prompt_with_all_patterns(
        self, script_generator_agent, sample_formula_patterns, sample_csa_terms, sample_margin_call
    ):
        """Test prompt building with complete pattern data."""
        prompt = script_generator_agent._build_generation_prompt(
            patterns=sample_formula_patterns,
            csa_terms=sample_csa_terms,
            margin_call=sample_margin_call,
            document_id="test_doc_123",
        )

        # Verify key elements present
        assert "test_doc_123" in prompt
        assert "Bank XYZ" in prompt
        assert "Hedge Fund ABC" in prompt
        assert "greatest_of" in prompt
        assert "rating_dependent" in prompt
        assert "Page 5" in prompt

    def test_build_prompt_minimal_data(
        self, script_generator_agent, sample_formula_patterns, sample_csa_terms
    ):
        """Test prompt building with minimal data (no margin call)."""
        prompt = script_generator_agent._build_generation_prompt(
            patterns=sample_formula_patterns,
            csa_terms=sample_csa_terms,
            margin_call=None,
            document_id=None,
        )

        # Should still work without optional data
        assert len(prompt) > 0
        assert "Bank XYZ" in prompt
        assert "greatest_of" in prompt

    def test_build_prompt_includes_guidance(
        self, script_generator_agent, sample_formula_patterns, sample_csa_terms
    ):
        """Test that prompt includes pattern-specific guidance."""
        prompt = script_generator_agent._build_generation_prompt(
            patterns=sample_formula_patterns,
            csa_terms=sample_csa_terms,
            margin_call=None,
            document_id="test",
        )

        # Should include requirements
        assert "valid Python syntax" in prompt.lower()
        assert "clause citations" in prompt.lower() or "page numbers" in prompt.lower()
        assert "helper functions" in prompt.lower() or "calculate" in prompt.lower()


# Test: Pattern-Specific Guidance
class TestPatternGuidance:
    """Tests for pattern-specific generation guidance."""

    def test_get_guidance_greatest_of(self, script_generator_agent):
        """Test guidance for greatest_of pattern."""
        guidance = script_generator_agent._get_pattern_specific_guidance(
            "greatest_of", ["moodys_csa", "sp_csa"]
        )

        assert "MAXIMUM" in guidance or "maximum" in guidance
        assert "moodys_csa" in guidance
        assert "sp_csa" in guidance

    def test_get_guidance_sum_of(self, script_generator_agent):
        """Test guidance for sum_of pattern."""
        guidance = script_generator_agent._get_pattern_specific_guidance(
            "sum_of", ["component_a", "component_b"]
        )

        assert "SUM" in guidance or "sum" in guidance

    def test_get_guidance_conditional(self, script_generator_agent):
        """Test guidance for conditional pattern."""
        guidance = script_generator_agent._get_pattern_specific_guidance("conditional", [])

        assert "conditional" in guidance.lower()
        assert "if" in guidance.lower() or "trigger" in guidance.lower()


# Test: Integration
class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_end_to_end_script_generation(
        self, script_generator_agent, sample_formula_patterns, sample_csa_terms, sample_margin_call
    ):
        """Test complete end-to-end script generation workflow."""
        # Mock valid response
        valid_script = '''"""
CSA AUDIT SCRIPT - test_doc_123
"""

def calculate_margin_requirement(net_exposure, posted_collateral, rating_scenario):
    """Calculate margin using greatest-of pattern."""
    # Delivery amount calculation (Page 5)
    moodys_csa = net_exposure - 0  # Simplified
    sp_csa = net_exposure - 0
    delivery_amount = max(moodys_csa, sp_csa)
    return delivery_amount
'''

        script_generator_agent._call_claude = AsyncMock(return_value={"raw_text": valid_script})

        # Execute full workflow
        result = await script_generator_agent.generate_audit_script(
            formula_patterns=sample_formula_patterns,
            csa_terms=sample_csa_terms,
            margin_call=sample_margin_call,
            document_id="test_doc_123",
        )

        # Verify result
        assert isinstance(result, str)
        assert len(result) > 100
        assert "def calculate_margin_requirement" in result

        # Verify reasoning chain completeness
        assert len(script_generator_agent.reasoning_chain) == 5
        step_names = [s.step_name for s in script_generator_agent.reasoning_chain]
        assert "build_prompt" in step_names
        assert "generate_script" in step_names
        assert "extract_code" in step_names
        assert "validate_syntax" in step_names
        assert "finalize" in step_names

        # Verify all steps have required fields
        for step in script_generator_agent.reasoning_chain:
            assert step.step_number > 0
            assert step.step_name
            assert step.model_used in ["rule-based", "sonnet", "haiku"]

    @pytest.mark.asyncio
    async def test_script_generation_with_invalid_syntax_raises_error(
        self, script_generator_agent, sample_formula_patterns, sample_csa_terms
    ):
        """Test that invalid syntax raises ValueError."""
        # Mock response with invalid Python
        invalid_script = """
def broken_function(
    # Missing closing parenthesis and colon
    return "broken"
"""

        script_generator_agent._call_claude = AsyncMock(return_value={"raw_text": invalid_script})

        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await script_generator_agent.generate_audit_script(
                formula_patterns=sample_formula_patterns,
                csa_terms=sample_csa_terms,
            )

        assert "syntax errors" in str(exc_info.value).lower()


# Test: Helper Methods
class TestHelperMethods:
    """Tests for helper methods."""

    def test_enhance_with_annotations(
        self, script_generator_agent, sample_formula_patterns
    ):
        """Test script enhancement with annotations."""
        original_script = "def test():\n    return 1"

        enhanced = script_generator_agent._enhance_with_annotations(
            original_script, sample_formula_patterns
        )

        # Currently returns as-is, but structure exists for future enhancements
        assert enhanced == original_script

    def test_reasoning_chain_tracks_all_steps(self, script_generator_agent):
        """Test that reasoning chain properly tracks steps."""
        script_generator_agent._clear_reasoning_chain()
        assert len(script_generator_agent.reasoning_chain) == 0

        script_generator_agent._add_reasoning_step(
            step_number=1,
            step_name="test_step",
            input_data={"foo": "bar"},
            output_data={"result": "success"},
            reasoning="Test reasoning",
            model_used="rule-based",
            confidence=0.95,
            duration_seconds=0.5,
        )

        assert len(script_generator_agent.reasoning_chain) == 1
        step = script_generator_agent.reasoning_chain[0]
        assert step.step_number == 1
        assert step.step_name == "test_step"
        assert step.confidence == 0.95
        assert step.duration_seconds == 0.5
