"""
Pipeline Orchestrator Service

Coordinates the full document processing pipeline: Parse -> Extract -> Normalize -> Map
Eliminates the need for users to manually orchestrate individual steps.
"""

import time
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from app.services.job_manager import JobManager, JobStatus, JobStep
from app.services.ade_service import ade_service
from app.services.collateral_normalizer import collateral_normalizer_service
from app.services.normalization_orchestrator import NormalizationOrchestrator
from app.services.ade_mapper import ade_mapper
from app.config import settings
from app.utils.file_storage import FileStorage


class ProcessOptions:
    """Configuration options for pipeline processing"""

    def __init__(
        self,
        normalize_method: str = "multi-agent",
        save_intermediate_steps: bool = False,
        calculate_margin: bool = False,
        portfolio_value: Optional[float] = None
    ):
        """
        Initialize process options.

        Args:
            normalize_method: "simple" or "multi-agent" (default: "multi-agent")
            save_intermediate_steps: Save intermediate files for debugging (default: False)
            calculate_margin: Run margin calculation as final step (default: False)
            portfolio_value: Portfolio value for margin calculation (required if calculate_margin=True)
        """
        self.normalize_method = normalize_method
        self.save_intermediate_steps = save_intermediate_steps
        self.calculate_margin = calculate_margin
        self.portfolio_value = portfolio_value

        # Validate
        if self.normalize_method not in ["simple", "multi-agent"]:
            raise ValueError(f"Invalid normalize_method: {normalize_method}. Must be 'simple' or 'multi-agent'")

        if self.calculate_margin and self.portfolio_value is None:
            raise ValueError("portfolio_value is required when calculate_margin=True")


class PipelineOrchestrator:
    """
    Orchestrates the complete document processing pipeline.

    Coordinates:
    1. Parse (ADE API)
    2. Extract (ADE API)
    3. Normalize (AI - simple or multi-agent)
    4. Map to CSATerms
    5. Calculate Margin (optional)

    Updates job state at each step for progress tracking.
    """

    def __init__(self, job_manager: JobManager):
        """
        Initialize pipeline orchestrator.

        Args:
            job_manager: Job manager for state tracking
        """
        self.job_manager = job_manager
        self.normalization_orchestrator = NormalizationOrchestrator(api_key=settings.anthropic_api_key)

    async def run_pipeline(
        self,
        job_id: str,
        document_id: str,
        options: ProcessOptions
    ) -> Dict[str, Any]:
        """
        Execute the complete processing pipeline.

        This is the main entry point for unified document processing.

        Args:
            job_id: Job identifier for tracking
            document_id: Document to process
            options: Processing configuration

        Returns:
            Complete pipeline results including CSATerms

        Raises:
            Exception: If any pipeline step fails
        """
        pipeline_start = time.time()

        try:
            # Update job to processing
            self.job_manager.update_job(
                job_id,
                status=JobStatus.PROCESSING,
                current_step=JobStep.PARSE,
                progress=0
            )

            # Step 1: Parse (20% progress)
            parse_result = await self._run_parse(job_id, document_id, options)
            parse_time = time.time() - pipeline_start

            self.job_manager.update_job(
                job_id,
                current_step=JobStep.EXTRACT,
                progress=20,
                results={"parse_id": parse_result["parse_id"]},
                step_timing={"parse": parse_time}
            )

            # Step 2: Extract (40% progress)
            extract_start = time.time()
            extract_result = await self._run_extract(job_id, parse_result, options)
            extract_time = time.time() - extract_start

            self.job_manager.update_job(
                job_id,
                current_step=JobStep.NORMALIZE,
                progress=40,
                results={"extraction_id": extract_result["extraction_id"]},
                step_timing={"extract": extract_time}
            )

            # Step 3: Normalize (70% progress)
            normalize_start = time.time()
            normalize_result = await self._run_normalize(
                job_id,
                extract_result,
                parse_result,
                options
            )
            normalize_time = time.time() - normalize_start

            self.job_manager.update_job(
                job_id,
                current_step=JobStep.MAP,
                progress=70,
                results={
                    "normalized_collateral_id": normalize_result.document_id,
                    "normalization_metadata": normalize_result.normalization_metadata
                },
                step_timing={"normalize": normalize_time}
            )

            # Step 4: Map to CSATerms (90% progress)
            map_start = time.time()
            csa_terms = await self._run_map(
                job_id,
                document_id,
                extract_result,
                normalize_result,
                options
            )
            map_time = time.time() - map_start

            self.job_manager.update_job(
                job_id,
                current_step=JobStep.DONE,
                progress=90,
                results={
                    "csa_terms_id": document_id,
                    "csa_terms": csa_terms.model_dump(mode="json")
                },
                step_timing={"map": map_time}
            )

            # Step 5: Calculate Margin (optional, 100% progress)
            if options.calculate_margin:
                calc_start = time.time()
                margin_call = await self._run_calculate(job_id, csa_terms, options)
                calc_time = time.time() - calc_start

                self.job_manager.update_job(
                    job_id,
                    results={"margin_call": margin_call},
                    step_timing={"calculate": calc_time}
                )

            # Mark as completed
            total_time = time.time() - pipeline_start
            self.job_manager.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                current_step=JobStep.DONE,
                progress=100,
                step_timing={"total": total_time}
            )

            # Return final job state
            return self.job_manager.get_job(job_id)

        except Exception as e:
            # Mark as failed
            self.job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                error={
                    "step": self.job_manager.get_job(job_id).get("current_step", "unknown"),
                    "message": str(e)
                }
            )
            raise

    async def _run_parse(
        self,
        job_id: str,
        document_id: str,
        options: ProcessOptions
    ) -> Dict[str, Any]:
        """
        Step 1: Parse PDF document using ADE.

        Args:
            job_id: Job identifier
            document_id: Document to parse
            options: Processing options

        Returns:
            Parse result with parse_id
        """
        # Find PDF file
        pdf_files = [f for f in Path(settings.pdf_dir).iterdir() if f.name.startswith(document_id)]

        if not pdf_files:
            raise FileNotFoundError(f"Document not found: {document_id}")

        pdf_path = str(pdf_files[0])

        # Parse document
        # NOTE: Always save parsed document (required for extract step)
        parse_result = ade_service.parse_document(
            pdf_path=pdf_path,
            document_id=document_id,
            save_parsed=True  # Always save - needed for extraction
        )

        if parse_result.get("status") == "error":
            raise RuntimeError(f"Parse failed: {parse_result.get('error')}")

        return parse_result

    async def _run_extract(
        self,
        job_id: str,
        parse_result: Dict[str, Any],
        options: ProcessOptions
    ) -> Dict[str, Any]:
        """
        Step 2: Extract CSA terms using ADE.

        Args:
            job_id: Job identifier
            parse_result: Result from parse step
            options: Processing options

        Returns:
            Extraction result with extraction_id
        """
        # NOTE: Always save extraction (required for normalize/map steps)
        extract_result = ade_service.extract_fields(
            parse_id=parse_result["parse_id"],
            field_schema=None,  # Use default schema
            save_extraction=True  # Always save - needed for normalization
        )

        if extract_result.get("status") == "error":
            raise RuntimeError(f"Extract failed: {extract_result.get('error')}")

        return extract_result

    async def _run_normalize(
        self,
        job_id: str,
        extract_result: Dict[str, Any],
        parse_result: Dict[str, Any],
        options: ProcessOptions
    ) -> Any:
        """
        Step 3: Normalize extracted data using AI.

        Args:
            job_id: Job identifier
            extract_result: Result from extract step
            parse_result: Result from parse step (for context)
            options: Processing options

        Returns:
            NormalizedCollateralTable (Pydantic model)
        """
        # Extract document_id from nested structure
        document_id = (
            extract_result.get("extraction_data", {}).get("document_id") or
            parse_result.get("parsed_data", {}).get("document_id")
        )

        if not document_id:
            raise RuntimeError("document_id not found in extract or parse results")

        extraction_id = extract_result["extraction_id"]

        if options.normalize_method == "multi-agent":
            # Use multi-agent orchestrator
            from app.models.normalized_collateral import (
                NormalizedCollateral,
                NormalizedCollateralTable,
                MaturityBucket,
                StandardizedCollateralType
            )

            # Get extraction data for multi-agent orchestrator
            extraction_data = extract_result.get("extraction_data", extract_result)
            parsed_data = parse_result.get("parsed_data", parse_result)

            # Call multi-agent orchestrator
            normalize_result = await self.normalization_orchestrator.normalize_extraction(
                extraction=extraction_data,
                parsed_document=parsed_data
            )

            # Extract normalized items from collateral agent result
            collateral_agent_result = normalize_result.agent_results.get("collateral")
            if not collateral_agent_result:
                raise RuntimeError("Collateral agent did not produce results")

            normalized_items_raw = collateral_agent_result.data.get("normalized_items", [])

            # Get rating events from extraction data
            column_info = extraction_data.get("extracted_fields", {}).get("column_info", {})
            column_count = column_info.get("valuation_column_count", 1)
            rating_events = column_info.get("valuation_column_names", [])

            if column_count == 1 and not rating_events:
                rating_events = ["Base Valuation Percentage"]

            # Convert raw dicts to NormalizedCollateral Pydantic models
            collateral_items = []
            for item in normalized_items_raw:
                # Skip error items
                if "error" in item:
                    continue

                # Get the original collateral type description for base_description
                # This should be available from the item
                base_description = item.get("collateral_type", "")

                # Convert maturity buckets to MaturityBucket models
                maturity_buckets = []
                raw_buckets = item.get("maturity_buckets", [])

                for bucket in raw_buckets:
                    # Convert percentages to decimals
                    valuation_pct = bucket.get("valuation_percentage", 100.0)
                    haircut_pct = bucket.get("haircut_percentage", 0.0)

                    maturity_buckets.append(MaturityBucket(
                        min_years=bucket.get("min_maturity_years"),
                        max_years=bucket.get("max_maturity_years"),
                        valuation_percentage=valuation_pct / 100.0,  # Convert to decimal
                        haircut=haircut_pct / 100.0,  # Convert to decimal
                        original_text=bucket.get("original_text")
                    ))

                # For items without maturity buckets, check if there's a flat percentage
                flat_valuation = None
                flat_haircut = None
                if not maturity_buckets and "valuation_percentage" in item:
                    # Single flat percentage
                    flat_valuation = item["valuation_percentage"] / 100.0
                    flat_haircut = (100.0 - item["valuation_percentage"]) / 100.0

                # Create NormalizedCollateral object
                try:
                    collateral_items.append(NormalizedCollateral(
                        standardized_type=StandardizedCollateralType(item.get("standardized_type")),
                        base_description=base_description,
                        maturity_buckets=maturity_buckets,
                        rating_event=item.get("rating_event"),
                        flat_valuation_percentage=flat_valuation,
                        flat_haircut=flat_haircut,
                        confidence=item.get("confidence"),
                        notes=item.get("summary")
                    ))
                except Exception as e:
                    print(f"Warning: Failed to create NormalizedCollateral from item: {e}")
                    print(f"Item data: {item}")
                    continue

            # Create NormalizedCollateralTable
            normalized_table = NormalizedCollateralTable(
                document_id=document_id,
                extraction_id=extraction_id,
                rating_events=rating_events,
                collateral_items=collateral_items,
                normalization_model="multi-agent",
                normalization_metadata={
                    "overall_confidence": normalize_result.overall_confidence,
                    "requires_human_review": normalize_result.requires_human_review,
                    "agents_used": normalize_result.processing_summary.agents_used,
                    "total_processing_time": normalize_result.processing_summary.total_processing_time_seconds
                }
            )

        else:
            # Use simple normalizer
            # Get the full extraction data needed for normalization
            extraction_data = extract_result.get("extraction_data", extract_result)

            # Call the correct method with proper parameters
            normalized_table = collateral_normalizer_service.normalize_collateral_table(
                ade_extraction=extraction_data,
                document_id=document_id,
                extraction_id=extraction_id
            )

        # Save to disk if requested
        if options.save_intermediate_steps:
            from app.utils.file_storage import FileStorage
            FileStorage.save_normalized_collateral(
                normalized_table,
                settings.normalized_collateral_dir
            )

        return normalized_table

    async def _run_map(
        self,
        job_id: str,
        document_id: str,
        extract_result: Dict[str, Any],
        normalized_table: Any,
        options: ProcessOptions
    ) -> Any:
        """
        Step 4: Map to CSATerms.

        Args:
            job_id: Job identifier
            document_id: Document identifier
            extract_result: Extraction result
            normalized_table: Normalized collateral table (NormalizedCollateralTable)
            options: Processing options

        Returns:
            CSATerms object
        """
        # Get the full extraction data
        extraction_data = extract_result.get("extraction_data", extract_result)

        # Map to CSATerms - FIXED parameter names to match actual signature
        csa_terms = ade_mapper.map_to_csa_terms(
            ade_extraction=extraction_data,                    # FIXED: was extraction_data
            document_id=document_id,                           # CORRECT
            normalized_collateral_table=normalized_table       # FIXED: was normalized_collateral
        )

        # Always save CSA terms (final output, not intermediate)
        from app.utils.file_storage import FileStorage
        FileStorage.save_csa_terms(csa_terms, settings.csa_terms_dir)

        return csa_terms

    async def _run_calculate(
        self,
        job_id: str,
        csa_terms: Dict[str, Any],
        options: ProcessOptions
    ) -> Dict[str, Any]:
        """
        Step 5: Calculate margin call (optional).

        Args:
            job_id: Job identifier
            csa_terms: CSA terms from map step
            options: Processing options

        Returns:
            Margin call calculation result
        """
        # TODO: Implement margin calculation
        # This would call a calculator service similar to other services
        # For now, return placeholder
        return {
            "portfolio_value": options.portfolio_value,
            "margin_required": 0.0,
            "status": "not_implemented"
        }


# Global orchestrator instance
_orchestrator = None

def get_pipeline_orchestrator(job_manager: Optional[JobManager] = None) -> PipelineOrchestrator:
    """
    Get global pipeline orchestrator instance (singleton pattern).

    Args:
        job_manager: Optional job manager (uses global if not provided)

    Returns:
        PipelineOrchestrator instance
    """
    global _orchestrator

    if _orchestrator is None:
        from app.services.job_manager import get_job_manager
        jm = job_manager or get_job_manager()
        _orchestrator = PipelineOrchestrator(jm)

    return _orchestrator
