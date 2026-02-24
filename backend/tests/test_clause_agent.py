"""
Unit tests for ClauseAgent - Formula Pattern Extraction

Tests verify pattern extraction logic, complexity scoring,
and integration with ADE extraction results.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.agents.clause_agent import ClauseAgent
from app.models.schemas import CSATerms
from app.models.formula_schemas import FormulaPattern, FormulaPatternResult


@pytest.fixture
def mock_api_key():
    """Mock API key for testing."""
    return "test_api_key_12345"


@pytest.fixture
def sample_ade_extraction():
    """Sample ADE extraction result with typical CSA structure."""
    return {
        "extraction_id": "extract_test_001",
        "extracted_fields": {
            "agreement_info": {
                "party_a": "CREDIT SUISSE INTERNATIONAL",
                "party_b": "FIFTH THIRD AUTO TRUST 2008-1"
            },
            "core_margin_terms": {
                "party_a_threshold": "Infinity",
                "party_b_threshold": "Not Applicable",
                "party_a_min_transfer_amount": "$50,000",
                "party_b_min_transfer_amount": "$50,000",
                "rounding": "Delivery Amount rounded up to nearest $1,000",
                "base_currency": "USD",
                "independent_amount": "Not Applicable"
            },
            "eligible_collateral_table": [
                {"type": "US Treasury Securities", "moodys_first": "100%"},
                {"type": "Corporate Bonds", "moodys_first": "95%"}
            ],
            "column_info": {
                "valuation_column_count": 4,
                "valuation_column_names": [
                    "Moody's First Trigger Event",
                    "Moody's Second Trigger Event",
                    "S&P Approved Ratings Downgrade",
                    "S&P Required Ratings Downgrade"
                ]
            },
            "clauses_to_collect": {
                "delivery_amount_clause": [
                    "The 'Delivery Amount' applicable to Party B will equal the greater of (i) the Moody's Credit Support Amount and (ii) the S&P Credit Support Amount."
                ],
                "return_amount_clause": [
                    "The 'Return Amount' applicable to Party B will equal the lesser of (i) the excess of Value of Credit Support above the Moody's Credit Support Amount and (ii) the excess above the S&P Credit Support Amount."
                ],
                "credit_support_amount_definition": [
                    "The 'Moody's Credit Support Amount' means (A) under First Trigger Event, the product of (i) the Mark-to-Market Exposure and (ii) 100%, minus (B) the Threshold, minus (C) any Independent Amount."
                ],
                "threshold_definition": [
                    "Threshold means, with respect to Party A, infinity. With respect to Party B, zero."
                ],
                "independent_amount_clause": [],
                "trigger_event_definitions": [
                    "First Trigger Event means Moody's long-term unsecured, unsubordinated debt rating falls below A2.",
                    "Second Trigger Event means Moody's rating falls below Baa2."
                ],
                "valuation_timing_clause": [
                    "Valuation Date means each Local Business Day."
                ],
                "dispute_resolution_clause": [
                    "Any dispute concerning a Valuation shall be resolved within two Business Days."
                ]
            }
        },
        "provenance": {
            "core_margin_terms.party_a_threshold": {
                "page": 4,
                "box": {"x": 100, "y": 200},
                "chunk_ids": ["chunk_001"]
            },
            "core_margin_terms.party_b_threshold": {
                "page": 4
            },
            "core_margin_terms.party_a_min_transfer_amount": {
                "page": 4
            },
            "eligible_collateral_table": {
                "page": 7
            },
            "clauses_to_collect.delivery_amount_clause": {
                "page": 3,
                "box": {"x": 100, "y": 200},
                "chunk_ids": ["chunk_delivery_001"]
            },
            "clauses_to_collect.return_amount_clause": {
                "page": 3,
                "box": {"x": 100, "y": 300},
                "chunk_ids": ["chunk_return_001"]
            }
        }
    }


@pytest.fixture
def sample_csa_terms():
    """Sample normalized CSA terms."""
    return CSATerms(
        document_id="test_doc_001",
        party_a_name="CREDIT SUISSE INTERNATIONAL",
        party_b_name="FIFTH THIRD AUTO TRUST 2008-1",
        party_a_threshold="infinity",
        party_b_threshold=0.0,
        party_a_mta=50000.0,
        party_b_mta=50000.0,
        party_a_threshold_currency="USD",
        party_b_threshold_currency="USD",
        party_a_mta_currency="USD",
        party_b_mta_currency="USD",
        rounding_amount=1000.0,
        rounding_direction="up",
        base_currency="USD",
        independent_amount="Not Applicable",
        eligible_collateral=[],
        valuation_percentage_type="single_value",
        rating_scenario_count=4,
        agreement_date="2008-01-15",
        valuation_date="T+1",
        valuation_time="Close of Business",
        notification_time="By 12:00 PM"
    )


class TestClauseAgentPatternExtraction:
    """Test pattern extraction from CSA documents."""

    @pytest.mark.asyncio
    @patch.object(ClauseAgent, '_call_claude', new_callable=AsyncMock)
    async def test_extract_delivery_amount_pattern_greatest_of(
        self,
        mock_call_claude,
        mock_api_key,
        sample_ade_extraction,
        sample_csa_terms
    ):
        """Test extraction of 'greatest_of' delivery amount pattern."""
        # Mock Claude response for delivery pattern
        mock_call_claude.return_value = {
            "pattern_type": "greatest_of",
            "components": ["moodys_csa", "sp_csa"],
            "confidence": 0.95,
            "reasoning": "Two rating agencies (Moody's and S&P) with 'greatest of' logic",
            "variations_detected": []
        }

        agent = ClauseAgent(mock_api_key)

        # Test delivery pattern extraction
        result = await agent._extract_delivery_amount_pattern(
            extracted_fields=sample_ade_extraction["extracted_fields"],
            column_info=sample_ade_extraction["extracted_fields"]["column_info"],
            csa_terms=sample_csa_terms,
            provenance=sample_ade_extraction["provenance"]
        )

        # Assertions
        assert result.pattern_name == "delivery_amount"
        assert result.pattern_type == "greatest_of"
        assert "moodys_csa" in result.components
        assert "sp_csa" in result.components
        assert result.confidence >= 0.9
        assert result.source_page == 4
        mock_call_claude.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_return_amount_pattern_mirrors_delivery(
        self,
        mock_api_key,
        sample_ade_extraction,
        sample_csa_terms
    ):
        """Test that return amount pattern mirrors delivery amount."""
        # Create delivery pattern
        delivery_pattern = FormulaPattern(
            pattern_name="delivery_amount",
            pattern_type="greatest_of",
            components=["moodys_csa", "sp_csa"],
            clause_text="Test clause",
            source_page=4,
            confidence=0.95,
            variations_detected=[]
        )

        agent = ClauseAgent(mock_api_key)

        # Test return pattern extraction
        result = await agent._extract_return_amount_pattern(
            delivery_pattern=delivery_pattern,
            extracted_fields=sample_ade_extraction["extracted_fields"],
            csa_terms=sample_csa_terms,
            provenance=sample_ade_extraction["provenance"]
        )

        # Assertions
        assert result.pattern_name == "return_amount"
        assert result.pattern_type == "greatest_of"  # Mirrors delivery
        assert result.components == delivery_pattern.components
        assert result.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_analyze_threshold_structure_asymmetric(
        self,
        mock_api_key,
        sample_ade_extraction,
        sample_csa_terms
    ):
        """Test analysis of asymmetric threshold structure."""
        agent = ClauseAgent(mock_api_key)

        result = await agent._analyze_threshold_structure(
            extracted_fields=sample_ade_extraction["extracted_fields"],
            csa_terms=sample_csa_terms,
            provenance=sample_ade_extraction["provenance"]
        )

        # Assertions
        assert result.structure_type in ["asymmetric", "variable_by_rating"]
        assert result.party_a_base == "infinity"
        assert result.party_b_base == 0.0
        assert result.confidence >= 0.9
        assert result.source_page == 4

    @pytest.mark.asyncio
    @patch.object(ClauseAgent, '_call_claude', new_callable=AsyncMock)
    async def test_analyze_haircut_structure_rating_dependent(
        self,
        mock_call_claude,
        mock_api_key,
        sample_ade_extraction,
        sample_csa_terms
    ):
        """Test analysis of rating-dependent haircut structure."""
        # Mock Claude response for haircut analysis
        mock_call_claude.return_value = {
            "dependency_type": "rating_dependent",
            "rating_scenarios": [
                "Moody's First Trigger Event",
                "Moody's Second Trigger Event",
                "S&P Approved Ratings Downgrade",
                "S&P Required Ratings Downgrade"
            ],
            "confidence": 0.92
        }

        agent = ClauseAgent(mock_api_key)

        result = await agent._analyze_haircut_structure(
            extracted_fields=sample_ade_extraction["extracted_fields"],
            column_info=sample_ade_extraction["extracted_fields"]["column_info"],
            csa_terms=sample_csa_terms,
            provenance=sample_ade_extraction["provenance"]
        )

        # Assertions
        assert result.dependency_type == "rating_dependent"
        assert "rating_scenario" in result.varies_by
        assert result.source_page == 7
        assert result.confidence >= 0.85
        assert result.rating_scenarios is not None

    @pytest.mark.asyncio
    async def test_extract_additional_rules(
        self,
        mock_api_key,
        sample_ade_extraction,
        sample_csa_terms
    ):
        """Test extraction of MTA, rounding, and independent amount rules."""
        agent = ClauseAgent(mock_api_key)

        mta_rules, rounding_rules, independent_amount = await agent._extract_additional_rules(
            extracted_fields=sample_ade_extraction["extracted_fields"],
            csa_terms=sample_csa_terms,
            provenance=sample_ade_extraction["provenance"]
        )

        # MTA Assertions
        assert mta_rules.party_a_mta == 50000.0
        assert mta_rules.party_b_mta == 50000.0
        assert mta_rules.structure_type == "fixed"
        assert mta_rules.source_page == 4

        # Rounding Assertions
        assert rounding_rules.rounding_method == "up"
        assert rounding_rules.rounding_increment == 1000.0
        assert "delivery_amount" in rounding_rules.applies_to

        # Independent Amount Assertions
        assert independent_amount.has_independent_amount is False


class TestComplexityScoring:
    """Test CSA complexity scoring logic."""

    def test_complexity_score_simple_csa(self, mock_api_key):
        """Test complexity scoring for simple CSA (single rating, fixed thresholds)."""
        agent = ClauseAgent(mock_api_key)

        delivery_pattern = FormulaPattern(
            pattern_name="delivery_amount",
            pattern_type="single_rating",
            components=["single_csa"],
            clause_text="Test",
            source_page=1,
            confidence=0.9,
            variations_detected=[]
        )

        threshold_structure = Mock(structure_type="fixed")
        haircut_structure = Mock(dependency_type="fixed")

        score = agent._calculate_complexity_score(
            delivery_pattern,
            threshold_structure,
            haircut_structure
        )

        # Simple CSA should have low complexity
        assert 0.0 <= score <= 0.3

    def test_complexity_score_moderate_csa(self, mock_api_key):
        """Test complexity scoring for moderate CSA (dual rating, asymmetric thresholds)."""
        agent = ClauseAgent(mock_api_key)

        delivery_pattern = FormulaPattern(
            pattern_name="delivery_amount",
            pattern_type="greatest_of",
            components=["moodys_csa", "sp_csa"],
            clause_text="Test",
            source_page=1,
            confidence=0.9,
            variations_detected=[]
        )

        threshold_structure = Mock(structure_type="asymmetric")
        haircut_structure = Mock(dependency_type="rating_dependent")

        score = agent._calculate_complexity_score(
            delivery_pattern,
            threshold_structure,
            haircut_structure
        )

        # Moderate CSA should have medium complexity
        assert 0.3 <= score <= 0.7

    def test_complexity_score_complex_csa(self, mock_api_key):
        """Test complexity scoring for complex CSA (conditional, variable thresholds, matrix haircuts)."""
        agent = ClauseAgent(mock_api_key)

        delivery_pattern = FormulaPattern(
            pattern_name="delivery_amount",
            pattern_type="conditional",
            components=["condition_a", "condition_b", "fallback"],
            clause_text="Test",
            source_page=1,
            confidence=0.9,
            variations_detected=[]
        )

        threshold_structure = Mock(structure_type="conditional")
        haircut_structure = Mock(dependency_type="matrix")

        score = agent._calculate_complexity_score(
            delivery_pattern,
            threshold_structure,
            haircut_structure
        )

        # Complex CSA should have high complexity
        assert 0.7 <= score <= 1.0


class TestHelperMethods:
    """Test helper methods."""

    def test_get_page_number_from_provenance(self, mock_api_key):
        """Test extraction of page numbers from provenance."""
        agent = ClauseAgent(mock_api_key)

        provenance = {
            "field.name": {"page": 5},
            "other.field": {"page": 7}
        }

        page = agent._get_page_number(provenance, "field.name")
        assert page == 5

        page = agent._get_page_number(provenance, "nonexistent.field")
        assert page == 0

    def test_construct_delivery_clause_text_dual_agency(self, mock_api_key):
        """Test construction of delivery clause text for dual agency pattern."""
        agent = ClauseAgent(mock_api_key)

        core_terms = {}
        column_names = [
            "Moody's First Trigger Event",
            "S&P Approved Ratings Downgrade"
        ]

        clause_text = agent._construct_delivery_clause_text(core_terms, column_names)

        assert "greatest" in clause_text.lower() or "Moody's" in clause_text
        assert "S&P" in clause_text or "greatest" in clause_text.lower()

    def test_compile_variations_summary(self, mock_api_key):
        """Test compilation of variations summary."""
        agent = ClauseAgent(mock_api_key)

        delivery_pattern = Mock(variations_detected=["Unusual component X"])
        return_pattern = Mock(variations_detected=["Asymmetric return logic"])
        threshold_structure = Mock(structure_type="conditional")
        haircut_structure = Mock(dependency_type="matrix")

        summary = agent._compile_variations_summary(
            delivery_pattern,
            return_pattern,
            threshold_structure,
            haircut_structure
        )

        assert "Unusual component X" in summary
        assert "Asymmetric return logic" in summary
        assert any("conditional" in s.lower() or "threshold" in s.lower() for s in summary)
        assert any("matrix" in s.lower() for s in summary)


class TestFullPatternExtraction:
    """Integration test for full pattern extraction."""

    @pytest.mark.asyncio
    @patch.object(ClauseAgent, '_call_claude', new_callable=AsyncMock)
    async def test_extract_patterns_end_to_end(
        self,
        mock_call_claude,
        mock_api_key,
        sample_ade_extraction,
        sample_csa_terms
    ):
        """Test full pattern extraction workflow."""
        # Mock Claude responses for different calls
        mock_call_claude.side_effect = [
            # Call 1: Delivery pattern extraction
            {
                "pattern_type": "greatest_of",
                "components": ["moodys_csa", "sp_csa"],
                "confidence": 0.95,
                "reasoning": "Dual rating agency structure",
                "variations_detected": []
            },
            # Call 2: Haircut structure analysis
            {
                "dependency_type": "rating_dependent",
                "rating_scenarios": ["Moody's First", "S&P Approved"],
                "confidence": 0.92
            }
        ]

        agent = ClauseAgent(mock_api_key)

        result = await agent.extract_patterns(
            document_id="test_doc_001",
            ade_extraction=sample_ade_extraction,
            csa_terms=sample_csa_terms,
            document_context=None
        )

        # Assertions on result structure
        assert isinstance(result, FormulaPatternResult)
        assert result.document_id == "test_doc_001"
        assert "delivery_amount" in result.patterns
        assert "return_amount" in result.patterns

        # Check delivery pattern
        assert result.patterns["delivery_amount"].pattern_type == "greatest_of"
        assert result.patterns["delivery_amount"].confidence >= 0.9

        # Check threshold structure
        assert result.threshold_structure is not None
        assert result.threshold_structure.party_a_base == "infinity"

        # Check haircut structure
        assert result.haircut_structure is not None
        assert result.haircut_structure.dependency_type == "rating_dependent"

        # Check MTA rules
        assert result.mta_rules.party_a_mta == 50000.0

        # Check complexity score
        assert 0.0 <= result.complexity_score <= 1.0

        # Check overall confidence
        assert 0.0 <= result.overall_confidence <= 1.0

        # Check reasoning chain
        assert result.agent_reasoning is not None
        assert len(result.agent_reasoning) >= 3  # At least 3 reasoning steps

        # Verify Claude was called
        assert mock_call_claude.call_count == 2

    @pytest.mark.asyncio
    @patch.object(ClauseAgent, '_call_claude', new_callable=AsyncMock)
    async def test_extract_patterns_uses_actual_clause_text(
        self,
        mock_call_claude,
        mock_api_key,
        sample_ade_extraction,
        sample_csa_terms
    ):
        """Test that clause agent uses actual extracted clause text instead of synthesized text."""
        # Mock Claude responses
        mock_call_claude.side_effect = [
            # Call 1: Delivery pattern extraction
            {
                "pattern_type": "greatest_of",
                "components": ["moodys_csa", "sp_csa"],
                "confidence": 0.95,
                "reasoning": "Dual rating agency structure",
                "variations_detected": []
            },
            # Call 2: Haircut structure analysis
            {
                "dependency_type": "rating_dependent",
                "rating_scenarios": ["Moody's First", "S&P Approved"],
                "confidence": 0.92
            }
        ]

        agent = ClauseAgent(mock_api_key)

        result = await agent.extract_patterns(
            document_id="test_doc_001",
            ade_extraction=sample_ade_extraction,
            csa_terms=sample_csa_terms
        )

        # Verify actual clause text is used (not synthesized)
        delivery_clause = result.patterns["delivery_amount"].clause_text
        assert "The 'Delivery Amount' applicable to Party B" in delivery_clause
        assert "[Synthesized]" not in delivery_clause
        assert "greater of" in delivery_clause
        assert "Moody's Credit Support Amount" in delivery_clause

        return_clause = result.patterns["return_amount"].clause_text
        assert "The 'Return Amount' applicable to Party B" in return_clause
        assert "[Synthesized]" not in return_clause
        assert "lesser of" in return_clause

        # Verify source pages come from clauses_to_collect provenance
        assert result.patterns["delivery_amount"].source_page == 3
        assert result.patterns["return_amount"].source_page == 3


class TestCSATypeLabeling:
    """Test CSA type labeling functionality."""

    def test_get_csa_type_label_dual_agency_greatest_of(self):
        """Test label for dual agency greatest_of pattern."""
        result = FormulaPatternResult(
            document_id="test",
            patterns={
                "delivery_amount": FormulaPattern(
                    pattern_name="delivery_amount",
                    pattern_type="greatest_of",
                    components=["moodys_csa", "sp_csa"],
                    clause_text="Test",
                    source_page=1,
                    confidence=0.9,
                    variations_detected=[]
                )
            },
            threshold_structure=Mock(),
            haircut_structure=Mock(),
            mta_rules=Mock(),
            rounding_rules=Mock(),
            complexity_score=0.5,
            overall_confidence=0.9
        )

        label = result.get_csa_type_label()
        assert label == "Dual Agency - Greatest Of"

    def test_get_csa_type_label_single_rating(self):
        """Test label for single rating agency pattern."""
        result = FormulaPatternResult(
            document_id="test",
            patterns={
                "delivery_amount": FormulaPattern(
                    pattern_name="delivery_amount",
                    pattern_type="single_rating",
                    components=["sp_csa"],
                    clause_text="Test",
                    source_page=1,
                    confidence=0.9,
                    variations_detected=[]
                )
            },
            threshold_structure=Mock(),
            haircut_structure=Mock(),
            mta_rules=Mock(),
            rounding_rules=Mock(),
            complexity_score=0.2,
            overall_confidence=0.9
        )

        label = result.get_csa_type_label()
        assert label == "Single Rating Agency"

    def test_assess_complexity_factors(self):
        """Test complexity factor breakdown."""
        result = FormulaPatternResult(
            document_id="test",
            patterns={
                "delivery_amount": FormulaPattern(
                    pattern_name="delivery_amount",
                    pattern_type="greatest_of",
                    components=["moodys_csa", "sp_csa"],
                    clause_text="Test",
                    source_page=1,
                    confidence=0.9,
                    variations_detected=[]
                )
            },
            threshold_structure=Mock(structure_type="variable_by_rating"),
            haircut_structure=Mock(dependency_type="matrix"),
            mta_rules=Mock(),
            rounding_rules=Mock(),
            complexity_score=0.75,
            overall_confidence=0.9
        )

        factors = result.assess_complexity_factors()

        assert "aggregation_complexity" in factors
        assert "threshold_complexity" in factors
        assert "haircut_complexity" in factors
        assert "overall_assessment" in factors
        assert factors["overall_assessment"] in ["Simple", "Moderate", "Complex"]
