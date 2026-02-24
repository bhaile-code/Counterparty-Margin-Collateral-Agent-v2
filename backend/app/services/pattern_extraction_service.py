"""
Service for extracting and managing formula patterns from CSA documents.

This service provides reusable functions for pattern extraction that can be
called from multiple endpoints (formula_analysis, script_generation, etc.)
"""

import logging
import time
from pathlib import Path
from typing import Optional, Tuple

from app.config import settings
from app.services.agents.clause_agent import ClauseAgent
from app.models.formula_schemas import FormulaPatternResult
from app.models.schemas import CSATerms
from app.utils.file_storage import FileStorage

logger = logging.getLogger(__name__)


class PatternExtractionService:
    """Service for extracting formula patterns from CSA documents."""

    def __init__(self, api_key: str):
        """
        Initialize the pattern extraction service.

        Args:
            api_key: Anthropic API key for Claude agent
        """
        self.api_key = api_key

    async def extract_or_load_patterns(
        self,
        document_id: str,
        force_reextract: bool = False
    ) -> Tuple[FormulaPatternResult, bool, float]:
        """
        Extract or load formula patterns for a document.

        This method checks if patterns already exist and loads them if available.
        Otherwise, it extracts new patterns using the Clause Agent.

        Args:
            document_id: CSA document identifier
            force_reextract: If True, re-extract even if patterns exist

        Returns:
            Tuple of (patterns, was_cached, extraction_time_seconds)
            - patterns: The extracted or loaded pattern result
            - was_cached: True if patterns were loaded from cache
            - extraction_time_seconds: Time taken for the operation

        Raises:
            FileNotFoundError: If required input data (ADE extraction, CSA terms) not found
            Exception: If pattern extraction fails
        """
        start_time = time.time()

        # Check if patterns already exist
        if not force_reextract:
            existing_patterns = FileStorage.load_json(
                settings.formula_patterns_dir,
                f"patterns_{document_id}"
            )
            if existing_patterns:
                logger.info(f"Using cached formula patterns for document {document_id}")
                patterns = FormulaPatternResult(**existing_patterns)
                elapsed = time.time() - start_time
                return patterns, True, elapsed

        # Need to extract patterns
        logger.info(f"Extracting formula patterns for document {document_id}")

        # Load required data - find the most recent extraction file
        extractions_path = Path(settings.extractions_dir)
        extraction_files = list(extractions_path.glob(f"extract_parse_{document_id}_*.json"))

        if not extraction_files:
            raise FileNotFoundError(
                f"ADE extraction not found for document {document_id}. "
                f"Please run document extraction first."
            )

        # Get the most recent extraction file
        latest_extraction_file = max(extraction_files, key=lambda f: f.stat().st_mtime)
        extraction_id = latest_extraction_file.stem

        ade_extraction = FileStorage.load_json(
            settings.extractions_dir,
            extraction_id
        )
        if not ade_extraction:
            raise FileNotFoundError(
                f"Failed to load extraction file {latest_extraction_file.name}"
            )

        csa_terms_data = FileStorage.load_json(
            settings.csa_terms_dir,
            f"csa_terms_{document_id}"
        )
        if not csa_terms_data:
            raise FileNotFoundError(
                f"CSA terms not found for document {document_id}. "
                f"Please run CSA mapping first."
            )

        # Parse CSA terms
        csa_terms = CSATerms(**csa_terms_data)

        # Optional: Load parsed document for additional context
        parsed_doc = FileStorage.load_json(
            settings.parsed_dir,
            f"parsed_{document_id}"
        )

        # Initialize Clause Agent
        agent = ClauseAgent(self.api_key)

        # Extract patterns
        logger.info(f"Running Clause Agent on document {document_id}")
        patterns = await agent.extract_patterns(
            document_id=document_id,
            ade_extraction=ade_extraction,
            csa_terms=csa_terms,
            document_context=parsed_doc
        )

        # Save result
        FileStorage.save_json(
            patterns.dict(),
            settings.formula_patterns_dir,
            f"patterns_{document_id}"
        )

        elapsed = time.time() - start_time
        logger.info(
            f"Pattern extraction completed for {document_id} in {elapsed:.2f}s. "
            f"Pattern type: {patterns.patterns.get('delivery_amount', {}).pattern_type if 'delivery_amount' in patterns.patterns else 'unknown'}, "
            f"Complexity: {patterns.complexity_score:.2f}"
        )

        return patterns, False, elapsed

    async def get_patterns(self, document_id: str) -> Optional[FormulaPatternResult]:
        """
        Retrieve previously extracted patterns for a document.

        Args:
            document_id: CSA document identifier

        Returns:
            FormulaPatternResult if found, None otherwise
        """
        patterns_data = FileStorage.load_json(
            settings.formula_patterns_dir,
            f"patterns_{document_id}"
        )

        if not patterns_data:
            return None

        return FormulaPatternResult(**patterns_data)

    def patterns_exist(self, document_id: str) -> bool:
        """
        Check if patterns exist for a document.

        Args:
            document_id: CSA document identifier

        Returns:
            True if patterns exist, False otherwise
        """
        patterns_data = FileStorage.load_json(
            settings.formula_patterns_dir,
            f"patterns_{document_id}"
        )
        return patterns_data is not None
