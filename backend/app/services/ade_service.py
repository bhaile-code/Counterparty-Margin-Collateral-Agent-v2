"""
LandingAI ADE service for document parsing and field extraction.

This service handles the two-step workflow:
1. Document parsing (step 1) - Converts PDF to ADE-readable format
2. Field extraction (step 2) - Extracts specific CSA terms from parsed document

The service delegates to:
- FileStorage: For JSON file I/O operations
- ADEMapper: For transforming ADE output to internal models
- Normalizer: For parsing and cleaning data (via ADEMapper)
"""

import json
import logging
import os
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List

from app.config import settings
from app.models.schemas import CSATerms
from app.utils.file_storage import FileStorage
from app.services.ade_mapper import ADEMapper

logger = logging.getLogger(__name__)


class ADEService:
    """Service for interacting with LandingAI ADE API."""

    def __init__(self):
        """Initialize the ADE service with dependencies."""
        if not settings.landingai_api_key:
            logger.warning("LandingAI API key not configured")
            self.predictor = None
        else:
            logger.info("LandingAI ADE service initialized")
            self.predictor = (
                None  # Will be initialized per request with specific endpoint
            )

        # Load the CSA extraction schema
        self.schema = self._load_schema()
        if self.schema:
            logger.info("CSA extraction schema loaded successfully")

        # Initialize dependencies
        self.storage = FileStorage()
        self.mapper = ADEMapper()

    def _load_schema(self) -> Optional[Dict]:
        """Load the CSA extraction JSON schema."""
        try:
            schema_path = Path(__file__).parent / "csa_extraction_schema.json"
            with open(schema_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load extraction schema: {str(e)}")
            return None

    def parse_document(
        self, pdf_path: str, document_id: str, save_parsed: bool = True
    ) -> Dict[str, Any]:
        """
        Step 1: Parse a PDF document using LandingAI ADE.

        This converts the PDF into a format that ADE can extract fields from.
        The parsed document is saved for later extraction testing.

        Args:
            pdf_path: Path to the PDF file
            document_id: Unique identifier for the document
            save_parsed: Whether to save the parsed result to disk

        Returns:
            Dict containing:
                - parse_id: Unique ID for this parse operation
                - status: "success" or "error"
                - page_count: Number of pages parsed
                - parsed_data: The parsed document data
                - error: Error message if status is "error"
        """
        logger.info(f"Parsing document: {pdf_path}")

        try:
            # Check if file exists
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")

            # Generate unique parse ID
            parse_id = self.storage.generate_id("parse", document_id)

            # Get file info
            file_size = os.path.getsize(pdf_path)
            logger.info(f"Document size: {file_size} bytes")

            # Call LandingAI ADE Parse API
            api_url = settings.landingai_parse_url
            headers = {"Authorization": f"Bearer {settings.landingai_api_key}"}

            logger.info(f"Calling LandingAI Parse API: {api_url} (timeout: {settings.landingai_timeout}s)")
            start_time = time.time()

            with open(pdf_path, "rb") as pdf_file:
                files = {"document": pdf_file}
                response = requests.post(
                    api_url,
                    headers=headers,
                    files=files,
                    timeout=settings.landingai_timeout,
                )

            elapsed_time = time.time() - start_time
            logger.info(f"Parse API call completed in {elapsed_time:.2f} seconds")

            # Warn if approaching timeout threshold
            if elapsed_time > (settings.landingai_timeout * 0.8):
                logger.warning(
                    f"Parse API call took {elapsed_time:.2f}s, approaching timeout of {settings.landingai_timeout}s"
                )

            if response.status_code != 200:
                error_msg = f"Parse API error for document {document_id}: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

            result = response.json()
            logger.info(
                f"Parse API response received with {len(result.get('chunks', []))} chunks"
            )

            # Extract parsed data with chunks containing bounding boxes
            chunks = result.get("chunks", [])
            splits = result.get("splits", [])
            # splits is a list of page splits, so page_count is the length of splits
            page_count = len(splits) if isinstance(splits, list) else 0

            parsed_data = {
                "parse_id": parse_id,
                "document_id": document_id,
                "file_path": pdf_path,
                "file_size": file_size,
                "parsed_at": datetime.utcnow().isoformat(),
                "status": "parsed",
                "markdown": result.get("markdown", ""),
                "chunks": chunks,  # Contains IDs and grounding (page, box)
                "splits": splits,
                "page_count": page_count,
                "metadata": result.get("metadata", {}),
            }

            logger.info(
                f"Document parsed successfully: {page_count} pages, {len(chunks)} chunks"
            )

            # Save parsed document if requested
            if save_parsed:
                parsed_file_path = self.storage.save_json(
                    parsed_data, settings.parsed_dir, parse_id
                )
                parsed_data["saved_to"] = parsed_file_path

            return {
                "parse_id": parse_id,
                "status": "success",
                "page_count": parsed_data.get("page_count"),
                "parsed_data": parsed_data,
            }

        except Exception as e:
            logger.error(
                f"Error parsing document {document_id}: {str(e)}", exc_info=True
            )
            return {
                "parse_id": None,
                "status": "error",
                "error": str(e),
                "document_id": document_id,
            }

    def extract_fields(
        self,
        parse_id: str,
        field_schema: Optional[Dict] = None,
        save_extraction: bool = True,
    ) -> Dict[str, Any]:
        """
        Step 2: Extract CSA terms from a parsed document.

        This uses the parsed document from step 1 and extracts specific fields
        according to the provided schema.

        Args:
            parse_id: ID of the parsed document from step 1
            field_schema: Optional schema defining fields to extract
            save_extraction: Whether to save the extraction result to disk

        Returns:
            Dict containing:
                - extraction_id: Unique ID for this extraction
                - status: "success" or "error"
                - extracted_fields: Dictionary of extracted field values
                - confidence_scores: Confidence score for each field
                - provenance: Source location (page, section) for each field
                - error: Error message if status is "error"
        """
        logger.info(f"Extracting fields from parsed document: {parse_id}")

        try:
            # Load parsed document using storage
            parsed_data = self.storage.load_json(settings.parsed_dir, parse_id)

            if parsed_data is None:
                raise FileNotFoundError(f"Parsed document not found: {parse_id}")

            logger.info(f"Loaded parsed document: {parse_id}")

            # Use the loaded CSA extraction schema
            if field_schema is None:
                field_schema = self.schema

            # Validate schema is loaded before proceeding
            if field_schema is None:
                raise ValueError(
                    "Extraction schema not available. Schema file may be missing or failed to load."
                )

            # Generate unique extraction ID
            extraction_id = self.storage.generate_id("extract", parse_id)

            # Call LandingAI ADE Extract API
            api_url = settings.landingai_extract_url
            headers = {"Authorization": f"Bearer {settings.landingai_api_key}"}

            # Prepare markdown content for extraction
            markdown_content = parsed_data.get("markdown", "")
            if not markdown_content:
                logger.warning("No markdown content found in parsed document")

            logger.info(f"Calling LandingAI Extract API: {api_url} (timeout: {settings.landingai_timeout}s)")
            start_time = time.time()

            # POST markdown as file and schema as form data
            files = {"markdown": markdown_content.encode("utf-8")}
            data = {"schema": json.dumps(field_schema)}

            response = requests.post(
                api_url,
                headers=headers,
                files=files,
                data=data,
                timeout=settings.landingai_timeout,
            )

            elapsed_time = time.time() - start_time
            logger.info(f"Extract API call completed in {elapsed_time:.2f} seconds")

            # Warn if approaching timeout threshold
            if elapsed_time > (settings.landingai_timeout * 0.8):
                logger.warning(
                    f"Extract API call took {elapsed_time:.2f}s, approaching timeout of {settings.landingai_timeout}s"
                )

            if response.status_code != 200:
                error_msg = f"Extract API error for parse_id {parse_id}: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

            result = response.json()
            logger.info(f"Extract API response received")

            # Extract structured data and metadata
            extraction = result.get("extraction", {})
            extraction_metadata = result.get("extraction_metadata", {})

            # Build chunk ID to bbox mapping from parsed document chunks
            chunk_bbox_map = self._build_chunk_bbox_map(parsed_data.get("chunks", []))
            logger.info(f"Built bbox mapping for {len(chunk_bbox_map)} chunks")

            # Create provenance with bounding boxes linked via chunk references
            provenance = {}
            confidence_scores = {}

            def extract_provenance_recursive(metadata_dict, prefix=""):
                """Recursively extract provenance from nested extraction_metadata."""
                for field_name, field_data in metadata_dict.items():
                    full_field_name = f"{prefix}.{field_name}" if prefix else field_name

                    if isinstance(field_data, dict):
                        if "references" in field_data:
                            # This is a leaf field with references
                            references = field_data.get("references", [])
                            if references and references[0] in chunk_bbox_map:
                                chunk_info = chunk_bbox_map[references[0]]
                                provenance[full_field_name] = {
                                    "page": chunk_info.get("page"),
                                    "box": chunk_info.get("box"),
                                    "chunk_ids": references,
                                }
                            confidence_scores[full_field_name] = (
                                1.0  # ADE doesn't provide scores
                            )
                        else:
                            # This is a nested object, recurse
                            extract_provenance_recursive(field_data, full_field_name)

            extract_provenance_recursive(extraction_metadata)
            logger.info(f"Extracted provenance for {len(provenance)} fields")

            # Store the full extraction output
            extracted_fields = extraction

            extraction_data = {
                "extraction_id": extraction_id,
                "parse_id": parse_id,
                "document_id": parsed_data.get("document_id"),
                "extracted_at": datetime.utcnow().isoformat(),
                "field_schema": field_schema,
                "extracted_fields": extracted_fields,
                "confidence_scores": confidence_scores,
                "provenance": provenance,
                "status": "extracted",
            }

            # Save extraction if requested
            if save_extraction:
                extraction_file_path = self.storage.save_json(
                    extraction_data, settings.extractions_dir, extraction_id
                )
                extraction_data["saved_to"] = extraction_file_path

            return {
                "extraction_id": extraction_id,
                "status": "success",
                "extracted_fields": extracted_fields,
                "confidence_scores": confidence_scores,
                "provenance": provenance,
                "extraction_data": extraction_data,
            }

        except Exception as e:
            logger.error(
                f"Error extracting fields from parse_id {parse_id}: {str(e)}",
                exc_info=True,
            )
            return {
                "extraction_id": None,
                "status": "error",
                "error": str(e),
                "parse_id": parse_id,
            }

    def load_saved_extraction(self, extraction_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a previously saved extraction result.

        This allows testing with saved extractions without re-running ADE.

        Args:
            extraction_id: ID of the saved extraction

        Returns:
            Extraction data dict or None if not found
        """
        return self.storage.load_json(settings.extractions_dir, extraction_id)

    def load_saved_parse(self, parse_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a previously saved parse result.

        Args:
            parse_id: ID of the saved parse

        Returns:
            Parse data dict or None if not found
        """
        return self.storage.load_json(settings.parsed_dir, parse_id)

    def map_ade_to_csa_terms(
        self,
        ade_extraction: Dict[str, Any],
        document_id: str,
        extraction_id: str = None,
    ) -> CSATerms:
        """
        Map ADE extraction output (following schema_v1.json) to CSATerms model.

        This method delegates to the ADEMapper service.

        Args:
            ade_extraction: Raw extraction from ADE following the schema
            document_id: Document identifier
            extraction_id: Extraction identifier (optional, for backward compatibility)

        Returns:
            CSATerms object populated from ADE extraction
        """
        return self.mapper.map_to_csa_terms(ade_extraction, document_id)

    def _build_chunk_bbox_map(self, chunks: List[Dict]) -> Dict[str, Dict]:
        """
        Build mapping from chunk ID to bounding box coordinates.

        Args:
            chunks: List of chunk objects from parse API response

        Returns:
            Dictionary mapping chunk ID to dict with 'page' and 'box' keys

        Example:
            {
                "chunk-uuid-1": {
                    "page": 0,
                    "box": {"left": 0.26, "top": 0.08, "right": 0.74, "bottom": 0.11}
                }
            }
        """
        bbox_map = {}

        for chunk in chunks:
            chunk_id = chunk.get("id")
            grounding = chunk.get("grounding", {})

            if chunk_id and grounding:
                bbox_map[chunk_id] = {
                    "page": grounding.get("page"),
                    "box": grounding.get("box"),
                }

        return bbox_map


# Global service instance
ade_service = ADEService()
