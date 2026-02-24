"""
ADE Mapper - Transform LandingAI ADE extraction output to internal models.

This module handles the mapping from the ADE extraction schema (schema_v1.json)
to the internal CSATerms Pydantic model.
"""

import logging
from typing import Any, Dict, List, Optional

from app.models.schemas import CSATerms
from app.models.normalized_collateral import NormalizedCollateralTable
from app.utils.normalizer import (
    parse_currency,
    parse_date,
    parse_rounding_increment,
    normalize_counterparty_name,
)
from app.utils.constants import normalize_threshold, THRESHOLD_INFINITY, INFINITY_STRINGS
from math import inf

logger = logging.getLogger(__name__)


class ADEMapper:
    """Maps ADE extraction results to internal data models."""

    def _validate_infinity_extraction(
        self,
        raw_text: str,
        parsed_value: Optional[float],
        field_name: str
    ) -> Optional[float]:
        """
        Validate that infinity keywords in raw text are correctly parsed.

        This is a safety check to catch cases where the LLM or parser incorrectly
        extracts a numeric value when the text clearly starts with "Infinity".

        Args:
            raw_text: Original extracted text from ADE
            parsed_value: Value returned by parse_currency()
            field_name: Name of the field being validated (for logging)

        Returns:
            Corrected value if mismatch detected, otherwise original parsed_value
        """
        if not raw_text:
            return parsed_value

        raw_text_lower = str(raw_text).lower().strip()

        # Check if raw text STARTS with an infinity keyword
        starts_with_infinity = any(
            raw_text_lower.startswith(inf_str)
            for inf_str in INFINITY_STRINGS
        )

        # Check if parsed value is NOT infinity
        is_not_infinity = (
            parsed_value is not None and
            parsed_value != inf and
            parsed_value != float('inf')
        )

        # Mismatch detected: text says infinity but parser returned a number
        if starts_with_infinity and is_not_infinity:
            logger.warning(
                f"INFINITY MISMATCH DETECTED for {field_name}: "
                f"Raw text starts with infinity keyword ('{raw_text[:50]}...') "
                f"but parsed value is {parsed_value}. "
                f"Correcting to infinity using normalize_threshold()."
            )
            # Use rule-based detection to get the correct value
            corrected_value = normalize_threshold(raw_text)
            logger.info(f"Corrected {field_name} from {parsed_value} to {corrected_value}")
            return corrected_value

        return parsed_value

    def _normalize_currency(self, raw_currency: str) -> str:
        """
        Normalize currency names to standard codes.

        Handles common currency name variations and converts them to
        standard currency codes (e.g., "US Dollar" -> "USD").

        Args:
            raw_currency: Raw currency string from ADE extraction

        Returns:
            Normalized currency code (defaults to "USD" if unknown)
        """
        if not raw_currency:
            return "USD"

        # Normalize to lowercase for case-insensitive matching
        currency_lower = str(raw_currency).lower().strip()

        # Currency mapping table (aligned with CurrencyNormalizerAgent)
        currency_mappings = {
            "$": "USD",
            "usd": "USD",
            "us dollars": "USD",
            "us dollar": "USD",
            "united states dollars": "USD",
            "united states dollar": "USD",
            "dollar": "USD",
            "dollars": "USD",
            "eur": "EUR",
            "euro": "EUR",
            "euros": "EUR",
            "gbp": "GBP",
            "pound": "GBP",
            "pounds": "GBP",
            "british pound": "GBP",
            "sterling": "GBP",
            "jpy": "JPY",
            "yen": "JPY",
            "japanese yen": "JPY",
            "chf": "CHF",
            "swiss franc": "CHF",
            "cad": "CAD",
            "canadian dollar": "CAD",
            "aud": "AUD",
            "australian dollar": "AUD",
        }

        # Check if already a standard code (e.g., "USD")
        normalized = currency_mappings.get(currency_lower)
        if normalized:
            logger.debug(f"Normalized currency '{raw_currency}' -> '{normalized}'")
            return normalized

        # If not in mapping, assume it's already a standard code
        # (but convert to uppercase for consistency)
        result = raw_currency.upper()
        logger.debug(f"Currency '{raw_currency}' assumed to be standard code: '{result}'")
        return result

    def map_to_csa_terms(
        self,
        ade_extraction: Dict[str, Any],
        document_id: str,
        normalized_collateral_table: NormalizedCollateralTable,
    ) -> CSATerms:
        """
        Transform ADE extraction output to CSATerms model.

        IMPORTANT: Normalized collateral is REQUIRED. The normalization step
        must be completed before calling this method.

        Args:
            ade_extraction: Raw extraction from ADE following schema_v1.json
            document_id: Document identifier
            normalized_collateral_table: Normalized collateral table (REQUIRED)

        Returns:
            CSATerms object populated from ADE extraction and normalized collateral

        Raises:
            ValueError: If normalized_collateral_table is None or required fields are missing
        """
        logger.info("Mapping ADE extraction to CSATerms model")

        # Validate that normalized collateral is provided
        if normalized_collateral_table is None:
            raise ValueError(
                "Normalized collateral table is required for mapping. "
                "Please run normalization first: POST /api/v1/documents/normalize/{extraction_id}"
            )

        if not normalized_collateral_table.collateral_items:
            raise ValueError(
                f"Normalized collateral table for document {document_id} has no collateral items"
            )

        try:
            # Extract and normalize each section
            agreement_info = self._extract_agreement_info(ade_extraction)
            margin_terms = self._extract_margin_terms(ade_extraction)
            valuation_info = self._extract_valuation_info(ade_extraction)

            # Use normalized collateral directly
            eligible_collateral = normalized_collateral_table.collateral_items

            # Extract confidence scores from ADE extraction
            confidence_scores = ade_extraction.get("confidence_scores", {})

            # Extract source pages from provenance
            source_pages = {}
            provenance = ade_extraction.get("provenance", {})
            for field_key, field_provenance in provenance.items():
                if isinstance(field_provenance, dict) and "page" in field_provenance:
                    # Map dotted keys (e.g., "agreement_info.party_a") to simple keys
                    simple_key = field_key.split(".")[-1]
                    source_pages[simple_key] = field_provenance["page"]

            # Build CSATerms object with party-specific fields
            csa_terms = CSATerms(
                party_a=agreement_info.get("party_a"),
                party_b=agreement_info.get("party_b"),
                party_a_threshold=margin_terms["party_a_threshold"],
                party_b_threshold=margin_terms["party_b_threshold"],
                party_a_minimum_transfer_amount=margin_terms["party_a_minimum_transfer_amount"],
                party_b_minimum_transfer_amount=margin_terms["party_b_minimum_transfer_amount"],
                party_a_independent_amount=margin_terms["party_a_independent_amount"],
                party_b_independent_amount=margin_terms["party_b_independent_amount"],
                rounding=margin_terms["rounding"],
                currency=margin_terms["currency"],
                normalized_collateral_id=normalized_collateral_table.document_id,
                eligible_collateral=eligible_collateral,
                valuation_agent=valuation_info["valuation_agent"],
                effective_date=agreement_info["effective_date"],
                confidence_scores=confidence_scores,
                source_document_id=document_id,
                source_pages=source_pages,
            )

            logger.info(
                f"Successfully mapped ADE extraction to CSATerms for "
                f"Party A: {agreement_info.get('party_a')}, Party B: {agreement_info.get('party_b')} "
                f"with {len(eligible_collateral)} normalized collateral items"
            )
            return csa_terms

        except Exception as e:
            logger.error(f"Error mapping ADE extraction: {str(e)}", exc_info=True)
            raise

    def _extract_agreement_info(self, ade_extraction: Dict) -> Dict:
        """Extract and normalize agreement information."""
        # Handle nested structure - extraction data may be nested under "extracted_fields"
        if "extracted_fields" in ade_extraction:
            agreement_info = ade_extraction.get("extracted_fields", {}).get("agreement_info", {})
        else:
            agreement_info = ade_extraction.get("agreement_info", {})

        # Extract both parties - convert empty strings to None for Optional fields
        party_a = agreement_info.get("party_a") or None
        party_b = agreement_info.get("party_b") or None

        # Parse effective date
        date_str = agreement_info.get("agreement_date")
        effective_date = parse_date(date_str) if date_str else None

        logger.debug(
            f"Extracted agreement info - Party A: {party_a}, Party B: {party_b}, "
            f"Effective Date: {effective_date}"
        )

        return {
            "party_a": party_a,
            "party_b": party_b,
            "effective_date": effective_date,
        }

    def _extract_margin_terms(self, ade_extraction: Dict) -> Dict:
        """Extract and parse core margin terms."""
        # Handle nested structure
        if "extracted_fields" in ade_extraction:
            core_terms = ade_extraction.get("extracted_fields", {}).get("core_margin_terms", {})
        else:
            core_terms = ade_extraction.get("core_margin_terms", {})

        # Extract and normalize currency (e.g., "US Dollar" -> "USD")
        raw_currency = core_terms.get("base_currency", "USD")
        currency = self._normalize_currency(raw_currency)

        # Parse party-specific currency values for both parties
        # parse_currency returns None for "Not Applicable" and float('inf') for "Infinity"
        party_a_threshold_raw = core_terms.get("party_a_threshold", "0")
        party_b_threshold_raw = core_terms.get("party_b_threshold", "0")

        party_a_threshold = parse_currency(party_a_threshold_raw)
        party_b_threshold = parse_currency(party_b_threshold_raw)

        # VALIDATION: Check for infinity keyword mismatches
        # This catches cases where raw text starts with "Infinity" but parser returned a number
        party_a_threshold = self._validate_infinity_extraction(
            party_a_threshold_raw, party_a_threshold, "party_a_threshold"
        )
        party_b_threshold = self._validate_infinity_extraction(
            party_b_threshold_raw, party_b_threshold, "party_b_threshold"
        )
        party_a_minimum_transfer_amount = parse_currency(
            core_terms.get("party_a_min_transfer_amount", "0")
        )
        party_b_minimum_transfer_amount = parse_currency(
            core_terms.get("party_b_min_transfer_amount", "0")
        )

        # Parse rounding - try parse_rounding_increment first, fallback to parse_currency
        rounding_text = core_terms.get("rounding", "")
        rounding = parse_rounding_increment(rounding_text)
        if rounding is None or rounding == 0.0:
            # Fallback to parse_currency if no increment found
            rounding_fallback = parse_currency(rounding_text)
            if rounding_fallback and rounding_fallback > 0:
                rounding = rounding_fallback
            else:
                # Default to 1.0 if we can't parse rounding (rounding is required and must be > 0)
                logger.warning(
                    f"Could not parse rounding from '{rounding_text}', defaulting to 1.0"
                )
                rounding = 1.0

        # Parse independent amounts - check for party-specific first, fall back to single value
        party_a_independent_amount = parse_currency(
            core_terms.get("party_a_independent_amount")
        )
        party_b_independent_amount = parse_currency(
            core_terms.get("party_b_independent_amount")
        )

        # If party-specific values aren't available, use the single independent_amount for both
        if party_a_independent_amount is None and party_b_independent_amount is None:
            single_independent_amount = parse_currency(core_terms.get("independent_amount", "0"))
            party_a_independent_amount = single_independent_amount
            party_b_independent_amount = single_independent_amount

        # Return party-specific values
        # Note: threshold=None represents infinite threshold (no collateral required)
        # Other fields default to 0.0
        return {
            "party_a_threshold": party_a_threshold,  # Keep None for infinity
            "party_b_threshold": party_b_threshold,  # Keep None for infinity
            "party_a_minimum_transfer_amount": (
                party_a_minimum_transfer_amount if party_a_minimum_transfer_amount is not None else 0.0
            ),
            "party_b_minimum_transfer_amount": (
                party_b_minimum_transfer_amount if party_b_minimum_transfer_amount is not None else 0.0
            ),
            "party_a_independent_amount": (
                party_a_independent_amount if party_a_independent_amount is not None else 0.0
            ),
            "party_b_independent_amount": (
                party_b_independent_amount if party_b_independent_amount is not None else 0.0
            ),
            "rounding": rounding,  # Already validated to be > 0
            "currency": currency,
        }

    def _extract_valuation_info(self, ade_extraction: Dict) -> Dict:
        """Extract valuation and timing information."""
        # Handle nested structure
        if "extracted_fields" in ade_extraction:
            valuation_timing = ade_extraction.get("extracted_fields", {}).get("valuation_timing", {})
        else:
            valuation_timing = ade_extraction.get("valuation_timing", {})

        # Extract fields - convert empty strings to None for Optional fields
        valuation_agent = valuation_timing.get("valuation_agent") or None
        valuation_time = valuation_timing.get("valuation_time") or None
        notification_time = valuation_timing.get("notification_time") or None

        return {
            "valuation_agent": valuation_agent,
            "valuation_time": valuation_time,
            "notification_time": notification_time,
        }

    # NOTE: _extract_collateral_info() and _process_collateral_table() methods
    # have been removed. Collateral processing is now handled by the
    # AI-powered normalization service (CollateralNormalizerService).
    # Normalized collateral is passed directly to map_to_csa_terms().


# Global mapper instance
ade_mapper = ADEMapper()
