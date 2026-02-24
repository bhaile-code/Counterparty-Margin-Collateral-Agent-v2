"""
AI-Powered Collateral Normalization Service.

This service uses Claude API to intelligently parse and normalize
collateral table data from ADE extraction output, handling:
- Complex maturity bucket parsing (e.g., "99% (1-2yr), 98% (2-3yr)")
- Collateral type standardization
- Rating event mapping
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from app.config import settings
from app.models.normalized_collateral import (
    MaturityBucket,
    NormalizedCollateral,
    NormalizedCollateralTable,
    StandardizedCollateralType,
)

logger = logging.getLogger(__name__)


class CollateralNormalizerService:
    """Service for AI-powered collateral table normalization."""

    def __init__(self, anthropic_client: Optional[Anthropic] = None):
        """
        Initialize the normalization service.

        Args:
            anthropic_client: Optional Anthropic client. If not provided,
                            creates one using settings.anthropic_api_key
        """
        self.client = anthropic_client or Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-3-5-haiku-20241022"  # Fast and cost-effective

    def normalize_collateral_table(
        self, ade_extraction: Dict[str, Any], document_id: str, extraction_id: str
    ) -> NormalizedCollateralTable:
        """
        Normalize an entire collateral table from ADE extraction.

        Args:
            ade_extraction: Raw ADE extraction output
            document_id: Source document ID
            extraction_id: Source extraction ID

        Returns:
            NormalizedCollateralTable with parsed and structured data

        Raises:
            ValueError: If extraction data is invalid
            Exception: If normalization fails
        """
        logger.info(f"Starting collateral normalization for document {document_id}")

        # Extract relevant sections
        collateral_table = ade_extraction.get("extracted_fields", {}).get(
            "eligible_collateral_table", []
        )
        column_info = ade_extraction.get("extracted_fields", {}).get("column_info", {})

        if not collateral_table:
            raise ValueError("No collateral table found in extraction")

        rating_events = column_info.get("valuation_column_names", [])

        logger.info(
            f"Found {len(collateral_table)} collateral rows with "
            f"{len(rating_events)} rating events"
        )

        # Normalize each row
        normalized_items = []
        for idx, row_data in enumerate(collateral_table):
            try:
                row = row_data.get("eligible_collateral_row", {})
                collateral_type = row.get("collateral_type", "")
                valuation_percentages = row.get("valuation_percentages", [])

                if not collateral_type:
                    logger.warning(f"Skipping empty collateral type at row {idx}")
                    continue

                # Normalize this row for each rating event
                for event_idx, event_name in enumerate(rating_events):
                    if event_idx < len(valuation_percentages):
                        valuation_str = valuation_percentages[event_idx]

                        normalized_item = self._normalize_collateral_row(
                            collateral_type=collateral_type,
                            valuation_string=valuation_str,
                            rating_event=event_name,
                        )

                        if normalized_item:
                            normalized_items.append(normalized_item)

            except Exception as e:
                logger.error(
                    f"Error normalizing collateral row {idx}: {str(e)}", exc_info=True
                )
                continue

        logger.info(f"Successfully normalized {len(normalized_items)} collateral items")

        # Build the final table
        return NormalizedCollateralTable(
            document_id=document_id,
            extraction_id=extraction_id,
            rating_events=rating_events,
            collateral_items=normalized_items,
            normalized_at=datetime.utcnow(),
            normalization_model=self.model,
            normalization_metadata={
                "total_rows_processed": len(collateral_table),
                "successful_normalizations": len(normalized_items),
                "rating_events_count": len(rating_events),
            },
        )

    def _normalize_collateral_row(
        self, collateral_type: str, valuation_string: str, rating_event: str
    ) -> Optional[NormalizedCollateral]:
        """
        Normalize a single collateral row using Claude API.

        Args:
            collateral_type: Raw collateral type description
            valuation_string: Valuation percentage string (may include maturity buckets)
            rating_event: Rating event name this applies to

        Returns:
            NormalizedCollateral object, or None if normalization fails
        """
        logger.debug(
            f"Normalizing: type='{collateral_type[:50]}...', "
            f"valuation='{valuation_string}', event='{rating_event}'"
        )

        try:
            # Build the prompt
            prompt = self._build_normalization_prompt(collateral_type, valuation_string)

            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0,  # Deterministic for parsing
                system=self._get_system_prompt(),
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            response_text = response.content[0].text
            normalized_data = json.loads(response_text)

            # Build NormalizedCollateral object
            return self._build_normalized_collateral(
                normalized_data=normalized_data,
                base_description=collateral_type,
                rating_event=rating_event,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error in normalization: {str(e)}", exc_info=True)
            return None

    def _get_system_prompt(self) -> str:
        """Get the system prompt for Claude."""
        return """You are a financial document parser specialized in ISDA Credit Support Annex (CSA) agreements. Your task is to parse collateral table entries and extract structured information.

You will be given:
1. A collateral type description (e.g., "Cash: US Dollars in depository account form.")
2. A valuation percentage string that may contain maturity buckets (e.g., "99% (1-2yr), 98% (2-3yr), 97%(3-5yr)")

Your job is to:
1. Standardize the collateral type to one of the predefined categories
2. Parse any maturity buckets from the valuation string
3. Calculate haircuts (haircut = 1 - valuation_percentage)
4. Return structured JSON

IMPORTANT RULES:
- Maturity bucket format: "99% (1-2yr)" means 99% valuation for 1 to 2 year maturity
- Format like "(1-2yr)" means minimum 1 year, maximum 2 years
- Format like ">20yr" means minimum 20 years, no maximum (use null)
- Format like "<1yr" means no minimum (use null), maximum 1 year
- IF NO MATURITY IS MENTIONED: Use a single bucket with min_years=null and max_years=null (applies to all maturities)
- Some entries have no maturity buckets (e.g., cash) - just a single percentage with no buckets
- "% to be determined" means unknown - set all values to null
- Calculate haircut as: 1 - valuation_percentage
- IF COLLATERAL TYPE DOESN'T CLEARLY MAP: Use "UNKNOWN" type and add a note that it requires user review

You must respond with ONLY valid JSON, no other text."""

    def _build_normalization_prompt(
        self, collateral_type: str, valuation_string: str
    ) -> str:
        """Build the user prompt for normalization."""
        available_types = [t.value for t in StandardizedCollateralType]

        return f"""Parse this collateral entry:

**Collateral Type**: {collateral_type}
**Valuation String**: {valuation_string}

Return a JSON object with this exact structure:
{{
  "standardized_type": "<one of: {', '.join(available_types)}>",
  "has_maturity_buckets": true or false,
  "maturity_buckets": [
    {{
      "min_years": <number or null>,
      "max_years": <number or null>,
      "valuation_percentage": <decimal 0.0-1.0>,
      "haircut": <decimal 0.0-1.0>,
      "original_text": "<the text this was parsed from>"
    }}
  ],
  "flat_valuation_percentage": <decimal 0.0-1.0, only if no maturity buckets>,
  "flat_haircut": <decimal 0.0-1.0, only if no maturity buckets>,
  "confidence": <decimal 0.0-1.0>,
  "notes": "<any warnings or special observations>"
}}

Examples:

Input: "Cash: US Dollars", "100%"
Output:
{{
  "standardized_type": "CASH_USD",
  "has_maturity_buckets": false,
  "maturity_buckets": [],
  "flat_valuation_percentage": 1.0,
  "flat_haircut": 0.0,
  "confidence": 1.0,
  "notes": null
}}

Input: "U.S. Treasury Securities with maturity 1-10 years", "99% (1-2yr), 98% (2-3yr), 97%(3-5yr), 96% (5-7yr), 94% (7-10yr)"
Output:
{{
  "standardized_type": "US_TREASURY",
  "has_maturity_buckets": true,
  "maturity_buckets": [
    {{"min_years": 1, "max_years": 2, "valuation_percentage": 0.99, "haircut": 0.01, "original_text": "1-2yr"}},
    {{"min_years": 2, "max_years": 3, "valuation_percentage": 0.98, "haircut": 0.02, "original_text": "2-3yr"}},
    {{"min_years": 3, "max_years": 5, "valuation_percentage": 0.97, "haircut": 0.03, "original_text": "3-5yr"}},
    {{"min_years": 5, "max_years": 7, "valuation_percentage": 0.96, "haircut": 0.04, "original_text": "5-7yr"}},
    {{"min_years": 7, "max_years": 10, "valuation_percentage": 0.94, "haircut": 0.06, "original_text": "7-10yr"}}
  ],
  "flat_valuation_percentage": null,
  "flat_haircut": null,
  "confidence": 0.95,
  "notes": null
}}

Now parse the provided entry and return ONLY the JSON object."""

    def _build_normalized_collateral(
        self, normalized_data: Dict[str, Any], base_description: str, rating_event: str
    ) -> NormalizedCollateral:
        """
        Build a NormalizedCollateral object from parsed data.

        Args:
            normalized_data: Parsed data from Claude
            base_description: Original collateral description
            rating_event: Rating event name

        Returns:
            NormalizedCollateral object
        """
        # Parse maturity buckets
        maturity_buckets = []
        for bucket_data in normalized_data.get("maturity_buckets", []):
            maturity_buckets.append(
                MaturityBucket(
                    min_years=bucket_data.get("min_years"),
                    max_years=bucket_data.get("max_years"),
                    valuation_percentage=bucket_data.get("valuation_percentage"),
                    haircut=bucket_data.get("haircut"),
                    original_text=bucket_data.get("original_text"),
                )
            )

        # Build the object
        return NormalizedCollateral(
            standardized_type=StandardizedCollateralType(
                normalized_data.get("standardized_type")
            ),
            base_description=base_description,
            maturity_buckets=maturity_buckets,
            rating_event=rating_event,
            flat_valuation_percentage=normalized_data.get("flat_valuation_percentage"),
            flat_haircut=normalized_data.get("flat_haircut"),
            confidence=normalized_data.get("confidence"),
            notes=normalized_data.get("notes"),
        )


# Global service instance
collateral_normalizer_service = CollateralNormalizerService()
