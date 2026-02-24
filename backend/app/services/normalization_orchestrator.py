"""
NormalizationOrchestrator - Coordinates all normalizer agents.

Responsibilities:
- Route fields to appropriate specialized agents
- Execute agents in parallel for maximum performance
- Aggregate results from all agents
- Run validation
- Calculate overall confidence and quality metrics
"""

import time
import asyncio
from typing import Dict, Any
from datetime import datetime

from app.services.agents import (
    CollateralNormalizerAgent,
    TemporalNormalizerAgent,
    CurrencyNormalizerAgent,
    ValidationAgent,
)
from app.models.agent_schemas import (
    NormalizedResult,
    ProcessingSummary,
)


class NormalizationOrchestrator:
    """
    Orchestrates multi-agent normalization system.

    Coordinates specialized agents for different field types and
    produces unified normalization result.
    """

    def __init__(self, api_key: str):
        self.collateral_agent = CollateralNormalizerAgent(api_key)
        self.temporal_agent = TemporalNormalizerAgent(api_key)
        self.currency_agent = CurrencyNormalizerAgent(api_key)
        self.validation_agent = ValidationAgent()

    async def normalize_extraction(
        self,
        extraction: Dict[str, Any],
        parsed_document: Dict[str, Any]
    ) -> NormalizedResult:
        """
        Main orchestration method.

        Process:
        1. Route fields to appropriate agents
        2. Execute agents in parallel for maximum performance
        3. Aggregate results
        4. Run validation
        5. Return unified result

        Args:
            extraction: Extracted fields from ADE
            parsed_document: Parsed document with chunks for context access

        Returns:
            NormalizedResult with all agent results and validation
        """
        start_time = time.time()

        # Generate IDs
        extraction_id = extraction.get("extraction_id", "unknown")
        document_id = extraction.get("document_id", "unknown")
        normalized_data_id = f"norm_{int(time.time()*1000)}"

        # Step 1: Route fields
        routed_fields = self._route_fields(extraction)

        # Step 2: Execute agents in parallel
        agent_results = {}
        agent_tasks = []
        agent_names = []

        # Collateral Agent
        if routed_fields.get("collateral"):
            agent_tasks.append(
                self.collateral_agent.normalize(
                    routed_fields["collateral"],
                    parsed_document
                )
            )
            agent_names.append("collateral")

        # Temporal Agent
        if routed_fields.get("temporal"):
            agent_tasks.append(
                self.temporal_agent.normalize(
                    routed_fields["temporal"],
                    parsed_document
                )
            )
            agent_names.append("temporal")

        # Currency Agent
        if routed_fields.get("currency"):
            agent_tasks.append(
                self.currency_agent.normalize(
                    routed_fields["currency"],
                    None  # Currency agent doesn't need document context
                )
            )
            agent_names.append("currency")

        # Execute all agents in parallel with error handling
        if agent_tasks:
            results = await asyncio.gather(*agent_tasks, return_exceptions=True)

            # Process results and handle errors
            for agent_name, result in zip(agent_names, results):
                if isinstance(result, Exception):
                    # Log error but don't fail entire pipeline
                    print(f"ERROR: {agent_name} agent failed: {result}")
                    # Create empty result for failed agent
                    agent_results[agent_name] = {
                        "error": str(result),
                        "agent_name": agent_name
                    }
                else:
                    agent_results[agent_name] = result

        # Step 3: Aggregate results
        aggregated_data = self._aggregate_results(agent_results)

        # Step 4: Run validation
        validation_report = await self.validation_agent.validate(aggregated_data)

        # Step 5: Calculate summary metrics
        processing_summary = self._create_processing_summary(
            agent_results,
            time.time() - start_time
        )

        # Step 6: Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(agent_results)

        # Step 7: Determine if human review needed
        requires_review = self._needs_human_review(
            agent_results,
            validation_report
        )

        return NormalizedResult(
            normalized_data_id=normalized_data_id,
            document_id=document_id,
            extraction_id=extraction_id,
            overall_confidence=overall_confidence,
            requires_human_review=requires_review,
            agent_results=agent_results,
            validation_report=validation_report,
            processing_summary=processing_summary,
            created_at=datetime.utcnow().isoformat()
        )

    def _route_fields(self, extraction: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Route extraction fields to appropriate agents.

        Args:
            extraction: Full extraction result from ADE

        Returns:
            Dict mapping agent names to their input data
        """
        routed = {}

        # Extract the nested extracted_fields dict
        extracted_fields = extraction.get("extracted_fields", {})

        # Collateral Agent - gets eligible collateral table
        eligible_collateral = extracted_fields.get("eligible_collateral_table", [])
        if eligible_collateral and isinstance(eligible_collateral, list):
            # Get column metadata for rating events
            column_info = extracted_fields.get("column_info", {})
            column_count = column_info.get("valuation_column_count", 1)
            column_names = column_info.get("valuation_column_names", [])

            # Transform to format expected by agent
            collateral_items = []

            if column_count == 1:
                # Simple case: single column, no row explosion
                # Use generic name for single valuation column
                for item in eligible_collateral:
                    row_data = item.get("eligible_collateral_row", {})
                    collateral_type = row_data.get("collateral_type", "")
                    valuation_pcts = row_data.get("valuation_percentages", [])

                    collateral_items.append({
                        "collateral_type": collateral_type,
                        "valuation_string": valuation_pcts[0] if valuation_pcts else "",
                        "rating_event": "Base Valuation Percentage",
                        "rating_event_order": 0
                    })
            else:
                # Complex case: multiple columns, explode rows
                # Create one item per (collateral_type, rating_event) pair
                for item in eligible_collateral:
                    row_data = item.get("eligible_collateral_row", {})
                    collateral_type = row_data.get("collateral_type", "")
                    valuation_pcts = row_data.get("valuation_percentages", [])

                    # Create one item per rating event column
                    for idx, rating_event_name in enumerate(column_names):
                        if idx < len(valuation_pcts):
                            collateral_items.append({
                                "collateral_type": collateral_type,
                                "valuation_string": valuation_pcts[idx],
                                "rating_event": rating_event_name,
                                "rating_event_order": idx
                            })

            routed["collateral"] = {
                "collateral_items": collateral_items,
                "rating_events": column_names if column_count > 1 else ["Base Valuation Percentage"],
                "rating_event_count": column_count,
                "is_multi_column": column_count > 1
            }

        # Temporal Agent - gets time and date fields from nested locations
        temporal_fields = {}

        # Get timing fields from valuation_timing
        valuation_timing = extracted_fields.get("valuation_timing", {})
        if "notification_time" in valuation_timing:
            temporal_fields["notification_time"] = valuation_timing["notification_time"]
        if "valuation_time" in valuation_timing:
            temporal_fields["valuation_time"] = valuation_timing["valuation_time"]

        # Get date fields from agreement_info
        agreement_info = extracted_fields.get("agreement_info", {})
        if "agreement_date" in agreement_info:
            temporal_fields["agreement_date"] = agreement_info["agreement_date"]
        if "signature_date" in agreement_info:
            temporal_fields["signature_date"] = agreement_info["signature_date"]

        if temporal_fields:
            routed["temporal"] = temporal_fields

        # Currency Agent - gets currency and amount fields from core_margin_terms
        currency_fields = {}
        core_margin_terms = extracted_fields.get("core_margin_terms", {})

        field_mapping = {
            "base_currency": "base_currency",
            "party_a_threshold": "party_a_threshold",
            "party_b_threshold": "party_b_threshold",
            "party_a_min_transfer_amount": "party_a_mta",
            "party_b_min_transfer_amount": "party_b_mta",
            "independent_amount": "independent_amount",
            "rounding": "rounding"
        }

        for out_field, in_field in field_mapping.items():
            if in_field in core_margin_terms:
                currency_fields[out_field] = core_margin_terms[in_field]

        if currency_fields:
            routed["currency"] = currency_fields

        return routed

    def _aggregate_results(
        self,
        agent_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Aggregate results from all agents into unified structure.

        Args:
            agent_results: Results from each agent

        Returns:
            Aggregated normalized data
        """
        aggregated = {}

        for agent_name, result in agent_results.items():
            # Extract normalized data from agent result
            if hasattr(result, 'data'):
                aggregated[agent_name] = result.data
            else:
                aggregated[agent_name] = result

        return aggregated

    def _calculate_overall_confidence(
        self,
        agent_results: Dict[str, Any]
    ) -> float:
        """
        Calculate weighted overall confidence from agent results.

        Args:
            agent_results: Results from each agent

        Returns:
            Overall confidence score (0.0-1.0)
        """
        confidences = []
        weights = {
            "collateral": 0.5,  # Collateral is most important
            "temporal": 0.25,
            "currency": 0.25,
        }

        for agent_name, result in agent_results.items():
            if hasattr(result, 'confidence'):
                confidence = result.confidence
                weight = weights.get(agent_name, 0.33)
                confidences.append((confidence, weight))

        if not confidences:
            return 0.8  # Default moderate confidence

        # Weighted average
        weighted_sum = sum(conf * weight for conf, weight in confidences)
        weight_sum = sum(weight for _, weight in confidences)

        return weighted_sum / weight_sum if weight_sum > 0 else 0.8

    def _needs_human_review(
        self,
        agent_results: Dict[str, Any],
        validation_report: Any
    ) -> bool:
        """
        Determine if human review is needed.

        Criteria:
        - Any agent flagged for review
        - Validation failed
        - Overall confidence too low

        Args:
            agent_results: Results from each agent
            validation_report: Validation report

        Returns:
            True if human review needed
        """
        # Check if any agent requires review
        for result in agent_results.values():
            if hasattr(result, 'requires_human_review') and result.requires_human_review:
                return True

        # Check if validation failed
        if not validation_report.passed:
            return True

        # Check overall confidence
        overall_confidence = self._calculate_overall_confidence(agent_results)
        if overall_confidence < 0.85:
            return True

        return False

    def _create_processing_summary(
        self,
        agent_results: Dict[str, Any],
        total_time: float
    ) -> ProcessingSummary:
        """
        Create summary of processing metrics.

        Args:
            agent_results: Results from each agent
            total_time: Total processing time in seconds

        Returns:
            ProcessingSummary
        """
        agents_used = list(agent_results.keys())

        total_reasoning_steps = 0
        total_self_corrections = 0
        models_used = set()
        context_accessed = False

        for result in agent_results.values():
            if hasattr(result, 'reasoning_chain'):
                total_reasoning_steps += len(result.reasoning_chain)

                # Collect models used
                for step in result.reasoning_chain:
                    models_used.add(step.model_used)

                    # Check if context was accessed
                    if step.step_name == "access_document_context":
                        context_accessed = True

            if hasattr(result, 'self_corrections'):
                total_self_corrections += result.self_corrections

        items_requiring_review = sum(
            1 for result in agent_results.values()
            if hasattr(result, 'requires_human_review') and result.requires_human_review
        )

        return ProcessingSummary(
            total_processing_time_seconds=total_time,
            agents_used=agents_used,
            total_reasoning_steps=total_reasoning_steps,
            total_self_corrections=total_self_corrections,
            models_used=list(models_used),
            context_accessed=context_accessed,
            items_requiring_review=items_requiring_review
        )
