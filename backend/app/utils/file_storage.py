"""File storage utility for JSON documents."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class InfinityEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles infinity values.

    Standard JSON doesn't support infinity. This encoder converts infinity
    floats to strings for JSON encoding and back:

    Serialization (Python -> JSON):
    - float('inf') -> "Infinity" (properly quoted in JSON)
    - float('-inf') -> "-Infinity" (properly quoted in JSON)
    - float('nan') -> null

    Deserialization (JSON -> Python):
    - "Infinity" -> float('inf')
    - "-Infinity" -> float('-inf')
    - null -> None

    The convert_infinity() method recursively processes data structures
    to replace all infinity floats with string representations that will
    be properly quoted by the standard JSON encoder.

    The parse_infinity() method does the reverse, converting strings back
    to Python infinity floats after JSON loading.
    """

    def encode(self, obj):
        """Override encode to pre-process infinity values."""
        converted = self.convert_infinity(obj)
        return super().encode(converted)

    @staticmethod
    def convert_infinity(obj):
        """Recursively convert infinity floats to strings.

        This pre-processes data before JSON encoding to ensure infinity
        values are converted to strings that will be properly quoted.

        Args:
            obj: Any Python object (dict, list, float, etc.)

        Returns:
            Same object structure with infinity floats replaced by strings
        """
        if isinstance(obj, float):
            if obj == float('inf'):
                return "Infinity"
            elif obj == float('-inf'):
                return "-Infinity"
            elif obj != obj:  # NaN check (NaN != NaN)
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: InfinityEncoder.convert_infinity(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [InfinityEncoder.convert_infinity(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(InfinityEncoder.convert_infinity(item) for item in obj)
        return obj

    @staticmethod
    def parse_infinity(obj):
        """Recursively convert 'Infinity' strings back to float('inf').

        This post-processes data after JSON loading to restore infinity
        values that were saved as strings.

        Args:
            obj: Any Python object (dict, list, str, etc.)

        Returns:
            Same object structure with "Infinity" strings replaced by float('inf')
        """
        if isinstance(obj, str):
            if obj == "Infinity":
                return float('inf')
            elif obj == "-Infinity":
                return float('-inf')
            return obj
        elif isinstance(obj, dict):
            return {k: InfinityEncoder.parse_infinity(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [InfinityEncoder.parse_infinity(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(InfinityEncoder.parse_infinity(item) for item in obj)
        return obj


class FileStorage:
    """Utility class for handling JSON file storage operations."""

    @staticmethod
    def save_json(data: Dict[str, Any], directory: str, filename: str) -> str:
        """
        Save data as JSON to specified directory.

        Args:
            data: Dictionary to save
            directory: Target directory path
            filename: Name of the file (without extension)

        Returns:
            Full path to the saved file

        Raises:
            IOError: If file cannot be written
        """
        try:
            # Ensure directory exists
            os.makedirs(directory, exist_ok=True)

            # Add .json extension if not present
            if not filename.endswith(".json"):
                filename = f"{filename}.json"

            file_path = os.path.join(directory, filename)

            # Pre-process data to convert infinity floats to strings
            data = InfinityEncoder.convert_infinity(data)

            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved JSON to: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Error saving JSON to {directory}/{filename}: {str(e)}")
            raise IOError(f"Failed to save JSON: {str(e)}")

    @staticmethod
    def load_json(directory: str, filename: str) -> Optional[Dict[str, Any]]:
        """
        Load JSON data from specified file.

        Post-processes loaded data to convert "Infinity" strings back to float('inf'),
        ensuring proper round-trip serialization of infinity values.

        Args:
            directory: Source directory path
            filename: Name of the file (without extension)

        Returns:
            Loaded dictionary or None if file not found

        Raises:
            IOError: If file exists but cannot be read
        """
        try:
            # Add .json extension if not present
            if not filename.endswith(".json"):
                filename = f"{filename}.json"

            file_path = os.path.join(directory, filename)

            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                return None

            with open(file_path, "r") as f:
                data = json.load(f)

            # Convert "Infinity" strings back to float('inf')
            data = InfinityEncoder.parse_infinity(data)

            logger.info(f"Loaded JSON from: {file_path}")
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {directory}/{filename}: {str(e)}")
            raise IOError(f"Invalid JSON file: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading JSON from {directory}/{filename}: {str(e)}")
            raise IOError(f"Failed to load JSON: {str(e)}")

    @staticmethod
    def generate_id(prefix: str, document_id: str) -> str:
        """
        Generate a unique ID with timestamp.

        This method creates IDs that chain together in the processing pipeline.
        Each step uses the previous step's ID as the base, creating a traceable chain.

        Args:
            prefix: Prefix for the ID (e.g., 'parse', 'extract', 'calc')
            document_id: Base document identifier (or previous step's ID for chaining)

        Returns:
            Generated ID in format: {prefix}_{document_id}_{timestamp}

        ID Chaining Pattern:
            1. Upload: document_id = "doc123"
            2. Parse: parse_id = generate_id("parse", document_id)
               -> "parse_doc123_20251105_143022"
            3. Extract: extraction_id = generate_id("extract", parse_id)
               -> "extract_parse_doc123_20251105_143022_20251105_143055"
            4. Calculate: calc_id = generate_id("calc", document_id)
               -> "calc_doc123_20251105_144000"

        Note: Some operations chain from previous IDs (parse -> extract),
        while others return to the original document_id (normalization, calculation).
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{document_id}_{timestamp}"

    @staticmethod
    def file_exists(directory: str, filename: str) -> bool:
        """
        Check if a file exists.

        Args:
            directory: Directory path
            filename: Name of the file

        Returns:
            True if file exists, False otherwise
        """
        if not filename.endswith(".json"):
            filename = f"{filename}.json"

        file_path = os.path.join(directory, filename)
        return os.path.exists(file_path)

    @staticmethod
    def list_files(directory: str) -> list[str]:
        """
        List all JSON files in a directory.

        Args:
            directory: Directory path

        Returns:
            List of filenames (without .json extension)
        """
        try:
            if not os.path.exists(directory):
                return []

            files = []
            for filename in os.listdir(directory):
                if filename.endswith(".json"):
                    # Remove .json extension
                    files.append(filename[:-5])

            return sorted(files)

        except Exception as e:
            logger.error(f"Error listing files in {directory}: {str(e)}")
            return []

    @staticmethod
    def save_normalized_collateral(
        normalized_table: "NormalizedCollateralTable", directory: str
    ) -> str:
        """
        Save a normalized collateral table.

        Args:
            normalized_table: NormalizedCollateralTable object to save
            directory: Target directory path

        Returns:
            Full path to the saved file

        Raises:
            IOError: If file cannot be written
        """
        from app.models.normalized_collateral import NormalizedCollateralTable

        # Generate filename based on document_id
        filename = f"normalized_{normalized_table.document_id}"

        # Convert to dict using Pydantic's model_dump
        data = normalized_table.model_dump(mode="json")

        return FileStorage.save_json(data, directory, filename)

    @staticmethod
    def load_normalized_collateral(
        document_id: str, directory: str
    ) -> Optional["NormalizedCollateralTable"]:
        """
        Load a normalized collateral table by document ID.

        Args:
            document_id: Document identifier
            directory: Source directory path

        Returns:
            NormalizedCollateralTable object or None if not found

        Raises:
            IOError: If file exists but cannot be read
        """
        from app.models.normalized_collateral import NormalizedCollateralTable

        filename = f"normalized_{document_id}"

        data = FileStorage.load_json(directory, filename)
        if data is None:
            return None

        # Parse with Pydantic
        return NormalizedCollateralTable(**data)

    @staticmethod
    def load_normalized_collateral_multiagent(
        document_id: str, directory: str
    ) -> Optional["NormalizedResult"]:
        """
        Load a multi-agent normalized result by document ID.

        Searches through all files in the normalized_multiagent directory
        to find the one matching the given document_id.

        Args:
            document_id: Document identifier to search for
            directory: Source directory path (normalized_multiagent/)

        Returns:
            NormalizedResult object or None if not found

        Raises:
            IOError: If directory cannot be read
            ValueError: If JSON is invalid or does not match NormalizedResult schema
        """
        from app.models.agent_schemas import NormalizedResult
        import os
        import json

        # Ensure directory exists
        if not os.path.exists(directory):
            logger.warning(f"Directory does not exist: {directory}")
            return None

        # Search through all JSON files in the directory
        try:
            for filename in os.listdir(directory):
                if not filename.endswith('.json'):
                    continue

                filepath = os.path.join(directory, filename)

                # Load and check document_id
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if data.get('document_id') == document_id:
                    logger.info(f"Found multi-agent normalized result: {filename}")
                    return NormalizedResult(**data)

        except Exception as e:
            logger.error(f"Error searching for multi-agent normalized result: {str(e)}")
            raise IOError(f"Failed to load multi-agent normalized result: {str(e)}")

        logger.warning(f"No multi-agent normalized result found for document_id: {document_id}")
        return None

    @staticmethod
    def convert_multiagent_to_collateral_table(
        multiagent_result: "NormalizedResult",
    ) -> "NormalizedCollateralTable":
        """
        Convert a multi-agent NormalizedResult to NormalizedCollateralTable format.

        This function transforms the multi-agent normalization output structure into
        the format expected by the mapper. Key transformations:
        - Extracts collateral data from agent_results
        - Converts maturity_buckets structure (min_maturity_years -> min_years)
        - Converts percentage scales (100.0 -> 1.0)
        - Adds required fields like base_description

        Args:
            multiagent_result: NormalizedResult from multi-agent normalization

        Returns:
            NormalizedCollateralTable compatible with mapper

        Raises:
            ValueError: If collateral agent data is missing or malformed
        """
        from app.models.normalized_collateral import (
            NormalizedCollateralTable,
            NormalizedCollateral,
            MaturityBucket,
        )
        from datetime import datetime

        logger.info(
            f"Converting multi-agent result {multiagent_result.normalized_data_id} to NormalizedCollateralTable"
        )

        # Extract collateral agent data
        if "collateral" not in multiagent_result.agent_results:
            raise ValueError("Multi-agent result missing 'collateral' agent data")

        collateral_agent = multiagent_result.agent_results["collateral"]
        collateral_data = collateral_agent.data

        if "normalized_items" not in collateral_data:
            raise ValueError(
                "Collateral agent data missing 'normalized_items' field"
            )

        normalized_items_raw = collateral_data["normalized_items"]

        # Convert each normalized item to NormalizedCollateral format
        collateral_items = []
        rating_events_set = set()

        for item_raw in normalized_items_raw:
            # Skip items missing required fields (normalization failures)
            if "standardized_type" not in item_raw:
                logger.warning(f"Skipping item missing standardized_type: {item_raw.get('summary', 'unknown')}")
                continue

            # Convert maturity buckets with field name mapping and percentage scaling
            maturity_buckets = []
            for bucket_raw in item_raw.get("maturity_buckets", []):
                # Multi-agent uses 100.0 for 100%, we need 1.0
                valuation_pct = bucket_raw.get("valuation_percentage", 100.0) / 100.0
                haircut_pct = bucket_raw.get("haircut_percentage", 0.0) / 100.0

                maturity_bucket = MaturityBucket(
                    min_years=bucket_raw.get("min_maturity_years"),  # Field name mapping
                    max_years=bucket_raw.get("max_maturity_years"),  # Field name mapping
                    valuation_percentage=valuation_pct,
                    haircut=haircut_pct,
                    original_text=bucket_raw.get("original_text"),
                )
                maturity_buckets.append(maturity_bucket)

            # Track rating events
            rating_event = item_raw.get("rating_event")
            if rating_event:
                rating_events_set.add(rating_event)

            # Create NormalizedCollateral object
            # Use standardized_type directly (multi-agent already outputs correct enum values)
            normalized_collateral = NormalizedCollateral(
                standardized_type=item_raw["standardized_type"],
                base_description=item_raw.get("summary", ""),  # Use summary as description
                maturity_buckets=maturity_buckets,
                rating_event=rating_event,
                flat_valuation_percentage=(
                    maturity_buckets[0].valuation_percentage
                    if maturity_buckets and not maturity_buckets[0].min_years
                    else None
                ),
                flat_haircut=(
                    maturity_buckets[0].haircut
                    if maturity_buckets and not maturity_buckets[0].min_years
                    else None
                ),
                confidence=item_raw.get("confidence"),
                notes=None,
            )
            collateral_items.append(normalized_collateral)

        # Create NormalizedCollateralTable
        collateral_table = NormalizedCollateralTable(
            document_id=multiagent_result.document_id,
            extraction_id=multiagent_result.extraction_id,
            rating_events=sorted(list(rating_events_set)),
            collateral_items=collateral_items,
            normalized_at=datetime.fromisoformat(
                multiagent_result.created_at.replace("Z", "+00:00")
            ),
            normalization_model="multi-agent",
            normalization_metadata={
                "multi_agent_id": multiagent_result.normalized_data_id,
                "overall_confidence": multiagent_result.overall_confidence,
                "requires_human_review": multiagent_result.requires_human_review,
                "processing_summary": multiagent_result.processing_summary.model_dump(),
            },
        )

        logger.info(
            f"Converted {len(collateral_items)} collateral items with "
            f"{len(rating_events_set)} rating events"
        )
        return collateral_table

    @staticmethod
    def save_csa_terms(csa_terms: "CSATerms", directory: str) -> str:
        """
        Save CSATerms object.

        Args:
            csa_terms: CSATerms object to save
            directory: Target directory path

        Returns:
            Full path to the saved file

        Raises:
            IOError: If file cannot be written
        """
        from app.models.schemas import CSATerms

        # Generate filename based on source_document_id
        filename = f"csa_terms_{csa_terms.source_document_id}"

        # Convert to dict using Pydantic's model_dump
        data = csa_terms.model_dump(mode="json")

        return FileStorage.save_json(data, directory, filename)

    @staticmethod
    def load_csa_terms(document_id: str, directory: str) -> Optional["CSATerms"]:
        """
        Load CSATerms by document ID.

        Args:
            document_id: Document identifier
            directory: Source directory path

        Returns:
            CSATerms object or None if not found

        Raises:
            IOError: If file exists but cannot be read
        """
        from app.models.schemas import CSATerms
        from app.models.normalized_collateral import NormalizedCollateral, MaturityBucket

        filename = f"csa_terms_{document_id}"

        data = FileStorage.load_json(directory, filename)
        if data is None:
            return None

        # Manually parse eligible_collateral dicts to avoid circular dependency
        # This ensures dicts from JSON are converted to NormalizedCollateral objects
        if "eligible_collateral" in data and data["eligible_collateral"]:
            parsed_collateral = []
            for item in data["eligible_collateral"]:
                if isinstance(item, dict):
                    # Parse maturity buckets first
                    if "maturity_buckets" in item and item["maturity_buckets"]:
                        item["maturity_buckets"] = [
                            MaturityBucket(**bucket) if isinstance(bucket, dict) else bucket
                            for bucket in item["maturity_buckets"]
                        ]
                    # Parse to NormalizedCollateral
                    parsed_collateral.append(NormalizedCollateral(**item))
                else:
                    # Already parsed (shouldn't happen, but handle it)
                    parsed_collateral.append(item)

            data["eligible_collateral"] = parsed_collateral
            logger.info(f"Parsed {len(parsed_collateral)} eligible collateral items for document {document_id}")

        # Parse with Pydantic
        return CSATerms(**data)

    @staticmethod
    def save_margin_call(
        margin_call: "MarginCall", directory: str, calculation_id: str
    ) -> str:
        """
        Save a MarginCall calculation result.

        Args:
            margin_call: MarginCall object to save
            directory: Target directory path
            calculation_id: Unique identifier for this calculation

        Returns:
            Full path to the saved file

        Raises:
            IOError: If file cannot be written
        """
        from app.models.schemas import MarginCall

        filename = f"margin_call_{calculation_id}"

        # Convert to dict using Pydantic's model_dump
        data = margin_call.model_dump(mode="json")

        return FileStorage.save_json(data, directory, filename)

    @staticmethod
    def load_margin_call(calculation_id: str, directory: str) -> Optional["MarginCall"]:
        """
        Load a MarginCall by calculation ID.

        Args:
            calculation_id: Calculation identifier
            directory: Source directory path

        Returns:
            MarginCall object or None if not found

        Raises:
            IOError: If file exists but cannot be read
        """
        from app.models.schemas import MarginCall

        filename = f"margin_call_{calculation_id}"

        data = FileStorage.load_json(directory, filename)
        if data is None:
            return None

        # Parse with Pydantic
        return MarginCall(**data)

    @staticmethod
    def save_explanation(
        explanation: Dict[str, Any], directory: str, calculation_id: str
    ) -> str:
        """
        Save a margin call explanation.

        Args:
            explanation: Explanation data dictionary (from LLM service)
            directory: Target directory path
            calculation_id: Calculation identifier this explanation is for

        Returns:
            Full path to the saved file

        Raises:
            IOError: If file cannot be written
        """
        filename = f"explanation_{calculation_id}"
        return FileStorage.save_json(explanation, directory, filename)

    @staticmethod
    def load_explanation(
        calculation_id: str, directory: str
    ) -> Optional[Dict[str, Any]]:
        """
        Load an explanation by calculation ID.

        Args:
            calculation_id: Calculation identifier
            directory: Source directory path

        Returns:
            Explanation dictionary or None if not found

        Raises:
            IOError: If file exists but cannot be read
        """
        filename = f"explanation_{calculation_id}"
        return FileStorage.load_json(directory, filename)

    @staticmethod
    def list_calculations_by_document(
        document_id: str, calculations_dir: str
    ) -> list[str]:
        """
        List all calculation IDs for a specific document.

        Args:
            document_id: Document identifier
            calculations_dir: Directory containing calculation files

        Returns:
            List of calculation IDs (sorted newest first by timestamp)
        """
        try:
            all_files = FileStorage.list_files(calculations_dir)

            # Filter for files that match this document
            # Format: margin_call_calc_{document_id}_{timestamp}
            matching_calcs = []
            for filename in all_files:
                # Remove 'margin_call_' prefix if present
                calc_id = filename.replace("margin_call_", "")

                # Check if this calculation belongs to the document
                # Format: calc_{document_id}_{timestamp}
                if calc_id.startswith(f"calc_{document_id}_"):
                    matching_calcs.append(calc_id)

            # Sort by timestamp (newest first)
            # Extract timestamp from calc_{document_id}_{timestamp}
            matching_calcs.sort(
                key=lambda x: x.split("_")[-1] if "_" in x else x,
                reverse=True
            )

            return matching_calcs

        except Exception as e:
            logger.error(f"Error listing calculations for document {document_id}: {str(e)}")
            return []

    @staticmethod
    def explanation_exists(calculation_id: str, directory: str) -> bool:
        """
        Check if an explanation exists for a calculation.

        Args:
            calculation_id: Calculation identifier
            directory: Explanations directory path

        Returns:
            True if explanation file exists, False otherwise
        """
        filename = f"explanation_{calculation_id}"
        return FileStorage.file_exists(directory, filename)

    @staticmethod
    def formula_pattern_exists(document_id: str, directory: str) -> bool:
        """
        Check if a formula pattern exists for a document.

        Args:
            document_id: Document identifier
            directory: Formula patterns directory path

        Returns:
            True if formula pattern file exists, False otherwise
        """
        filename = f"patterns_{document_id}"
        return FileStorage.file_exists(directory, filename)
