"""
CurrencyNormalizerAgent - Currency and amount standardization.

Implements 3-step reasoning chain:
1. Extract Amount and Currency - Parse amount and identify currency
2. Standardize to ISO - Convert to ISO 4217 codes
3. Validate Currency - Ensure currency code is valid
"""

import time
import json
import re
import asyncio
from typing import Dict, Any, Optional

from app.services.agents.base_agent import BaseNormalizerAgent
from app.models.agent_schemas import NormalizedCurrency
from app.utils.constants import normalize_threshold, THRESHOLD_INFINITY, INFINITY_STRINGS


class CurrencyNormalizerAgent(BaseNormalizerAgent):
    """
    Specialized agent for currency and amount normalization.

    Capabilities:
    - Parse various amount formats
    - Standardize to ISO 4217 currency codes
    - Handle special values (Infinity, Not Applicable)
    - Extract rounding rules with direction
    """

    def __init__(self, api_key: str):
        super().__init__(api_key)

        # ISO 4217 currency code mappings
        self.currency_mappings = {
            "$": "USD",
            "usd": "USD",
            "us dollars": "USD",
            "us dollar": "USD",
            "united states dollars": "USD",
            "dollar": "USD",
            "dollars": "USD",
            "€": "EUR",
            "eur": "EUR",
            "euro": "EUR",
            "euros": "EUR",
            "£": "GBP",
            "gbp": "GBP",
            "british pounds": "GBP",
            "british pound": "GBP",
            "pounds": "GBP",
            "pound": "GBP",
            "¥": "JPY",
            "jpy": "JPY",
            "yen": "JPY",
            "japanese yen": "JPY",
            "chf": "CHF",
            "swiss francs": "CHF",
            "swiss franc": "CHF",
        }

        # Valid ISO 4217 codes
        self.valid_iso_codes = [
            "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD",
            "HKD", "SGD", "SEK", "NOK", "DKK", "ZAR", "BRL", "MXN"
        ]

    async def normalize(
        self,
        data: Dict[str, Any],
        document_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main normalization entry point for currency/amount fields.

        Args:
            data: Dict with currency/amount fields to normalize
            document_context: Optional parsed document (not used for currency)

        Returns:
            Dict with normalized currency/amount fields
        """
        start_time = time.time()
        self._clear_reasoning_chain()

        normalized_fields = {}

        # Normalize currency fields in parallel
        currency_fields = [
            "base_currency",
            "party_a_threshold",
            "party_b_threshold",
            "party_a_min_transfer_amount",
            "party_b_min_transfer_amount",
            "independent_amount"
        ]

        tasks = []
        field_names = []

        for field_name in currency_fields:
            if field_name in data and data[field_name]:
                tasks.append(
                    self._normalize_currency_field(
                        field_name=field_name,
                        raw_value=data[field_name]
                    )
                )
                field_names.append(field_name)

        # Add rounding field to parallel processing if present
        if "rounding" in data and data["rounding"]:
            tasks.append(self._normalize_rounding_field(data["rounding"]))
            field_names.append("rounding")

        # Execute all field processing in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for field_name, result in zip(field_names, results):
                if isinstance(result, Exception):
                    print(f"ERROR: Failed to normalize currency field {field_name}: {result}")
                else:
                    normalized_fields[field_name] = result

        processing_time = time.time() - start_time

        return self._format_result(
            data=normalized_fields,
            processing_time=processing_time
        )

    async def _normalize_currency_field(
        self,
        field_name: str,
        raw_value: str
    ) -> NormalizedCurrency:
        """
        Normalize a single currency/amount field using 3-step reasoning.

        Args:
            field_name: Name of the field
            raw_value: Raw value string

        Returns:
            NormalizedCurrency object
        """
        # Step 1: Extract Amount and Currency
        extract_result = await self._step1_extract_amount_and_currency(raw_value)

        # Step 2: Standardize to ISO
        iso_result = self._step2_standardize_to_iso(extract_result)

        # Step 3: Validate Currency
        final_result = self._step3_validate_currency(
            field_name, raw_value, iso_result
        )

        return NormalizedCurrency(**final_result)

    async def _step1_extract_amount_and_currency(
        self,
        raw_value: str
    ) -> Dict[str, Any]:
        """
        Step 1: Extract amount and identify currency.

        Handles:
        - Numeric amounts with currency symbols
        - Text representations ("Two Million")
        - Special values ("Infinity", "Not Applicable", "N/A")

        Model: Rule-based pre-check, then Haiku if needed
        """
        step_start = time.time()

        # PRE-CHECK: Detect infinity strings before calling LLM
        # This handles "Infinity; provided that..." patterns correctly
        raw_value_lower = raw_value.lower().strip()

        # Check if the value STARTS with an infinity keyword (case-insensitive)
        # This ensures we catch "Infinity; provided that..." correctly
        for infinity_str in INFINITY_STRINGS:
            if raw_value_lower.startswith(infinity_str):
                # Found infinity at the start - return immediately without calling LLM
                result = {
                    "amount": None,
                    "currency_text": None,
                    "special_value": "infinity"
                }

                step_duration = time.time() - step_start
                self._add_reasoning_step(
                    step_number=1,
                    step_name="extract_amount_and_currency",
                    input_data={"raw_value": raw_value},
                    output_data=result,
                    reasoning=f"Detected infinity keyword '{infinity_str}' at start of value (pre-LLM check)",
                    model_used="rule-based",
                    duration_seconds=step_duration
                )
                return result

        # Check for N/A or Not Applicable patterns
        if raw_value_lower in ["n/a", "na", "not applicable", "none", "null", ""]:
            result = {
                "amount": None,
                "currency_text": None,
                "special_value": "not_applicable"
            }

            step_duration = time.time() - step_start
            self._add_reasoning_step(
                step_number=1,
                step_name="extract_amount_and_currency",
                input_data={"raw_value": raw_value},
                output_data=result,
                reasoning="Detected N/A or not applicable value (pre-LLM check)",
                model_used="rule-based",
                duration_seconds=step_duration
            )
            return result

        # If no special value detected, proceed with LLM parsing
        prompt = f"""Extract the amount and currency from this string.

Input: "{raw_value}"

Parse:
1. Numeric amount (remove commas, convert to number)
2. Currency identifier ($, USD, "US Dollars", etc.)
3. Special values (Infinity, Not Applicable, N/A)

IMPORTANT: If the text starts with "Infinity", "Unlimited", or similar terms, treat it as a special_value
regardless of any conditions or provisos that follow. Look at the FIRST word/concept only.

Return JSON:
{{
  "amount": 2000000.0 or null,
  "currency_text": "$" or "US Dollars" or null,
  "special_value": "infinity" or "not_applicable" or null
}}

Examples:
- "$2,000,000" → {{"amount": 2000000.0, "currency_text": "$"}}
- "Infinity" → {{"amount": null, "currency_text": null, "special_value": "infinity"}}
- "Not Applicable" → {{"amount": null, "currency_text": null, "special_value": "not_applicable"}}
- "USD 1,500,000" → {{"amount": 1500000.0, "currency_text": "USD"}}
- "Infinity; provided that if certain conditions apply, the Threshold shall be zero" → {{"amount": null, "currency_text": null, "special_value": "infinity"}}
"""

        response = await self._call_claude(prompt, model=self.haiku_model)

        step_duration = time.time() - step_start

        self._add_reasoning_step(
            step_number=1,
            step_name="extract_amount_and_currency",
            input_data={"raw_value": raw_value},
            output_data=response,
            reasoning="Extracted amount and currency identifier",
            model_used="haiku",
            duration_seconds=step_duration
        )

        return response

    def _step2_standardize_to_iso(
        self,
        extract_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 2: Standardize currency to ISO 4217 codes.

        Maps various currency representations to standard codes.
        Model: Rule-based
        """
        step_start = time.time()

        amount = extract_result.get("amount")
        currency_text = extract_result.get("currency_text")
        special_value = extract_result.get("special_value")

        # Handle special values
        if special_value == "infinity":
            result = {
                "amount": None,
                "currency_code": None,
                "is_infinity": True,
                "is_not_applicable": False
            }
        elif special_value == "not_applicable" or special_value == "n/a":
            result = {
                "amount": None,
                "currency_code": None,
                "is_infinity": False,
                "is_not_applicable": True
            }
        else:
            # Map currency text to ISO code
            currency_code = None
            if currency_text:
                currency_code = self._map_currency(currency_text)

            result = {
                "amount": amount,
                "currency_code": currency_code,
                "is_infinity": False,
                "is_not_applicable": False
            }

        step_duration = time.time() - step_start

        self._add_reasoning_step(
            step_number=2,
            step_name="standardize_to_iso",
            input_data={"currency_text": currency_text},
            output_data=result,
            reasoning=f"Mapped to ISO 4217 code: {result.get('currency_code')}" if result.get('currency_code') else "Handled special value",
            model_used="rule-based",
            duration_seconds=step_duration
        )

        return result

    def _step3_validate_currency(
        self,
        field_name: str,
        raw_value: str,
        iso_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 3: Validate currency code and amount.

        Checks:
        - Currency code is valid ISO 4217
        - Amount is non-negative (if applicable)

        Model: Rule-based
        """
        step_start = time.time()

        amount = iso_result.get("amount")
        currency_code = iso_result.get("currency_code")
        is_infinity = iso_result.get("is_infinity", False)
        is_not_applicable = iso_result.get("is_not_applicable", False)

        # Validate currency code
        is_valid = True
        if currency_code and currency_code not in self.valid_iso_codes:
            is_valid = False

        # Validate amount (should be non-negative)
        if amount is not None and amount < 0:
            is_valid = False

        step_duration = time.time() - step_start

        result = {
            "amount": amount,
            "currency_code": currency_code,
            "is_infinity": is_infinity,
            "is_not_applicable": is_not_applicable,
            "raw_value": raw_value,
            "confidence": 1.0 if is_valid else 0.7
        }

        self._add_reasoning_step(
            step_number=3,
            step_name="validate_currency",
            input_data={
                "currency_code": currency_code,
                "amount": amount
            },
            output_data={
                "valid": is_valid,
                "final_result": result
            },
            reasoning=f"Validation {'passed' if is_valid else 'failed'}",
            model_used="rule-based",
            confidence=result["confidence"],
            duration_seconds=step_duration
        )

        return result

    async def _normalize_rounding_field(
        self,
        raw_value: str
    ) -> Dict[str, Any]:
        """
        Normalize rounding field with direction extraction.

        Extracts:
        - Rounding amount
        - Direction (up/down)
        - Separate delivery and return rounding if specified

        Args:
            raw_value: Raw rounding string

        Returns:
            Dict with delivery_rounding and return_rounding
        """
        prompt = f"""Extract rounding information from this text.

Text: "{raw_value}"

Extract:
1. Delivery rounding amount and direction (up/down/nearest)
2. Return rounding amount and direction (may be different)
3. Currency

Return JSON:
{{
  "delivery_rounding": {{
    "amount": 10000,
    "direction": "up",
    "currency": "USD"
  }},
  "return_rounding": {{
    "amount": 10000,
    "direction": "down",
    "currency": "USD"
  }}
}}

Note: If only one rounding specified, use same for both delivery and return.
"""

        response = await self._call_claude(prompt, model=self.haiku_model)

        # Standardize currency codes in rounding
        if "delivery_rounding" in response:
            currency_text = response["delivery_rounding"].get("currency")
            if currency_text:
                response["delivery_rounding"]["currency"] = self._map_currency(currency_text)

        if "return_rounding" in response:
            currency_text = response["return_rounding"].get("currency")
            if currency_text:
                response["return_rounding"]["currency"] = self._map_currency(currency_text)

        return response

    def _map_currency(self, currency_text: str) -> Optional[str]:
        """
        Map currency text to ISO 4217 code.

        Args:
            currency_text: Currency string from text

        Returns:
            ISO 4217 code or original text if no mapping found
        """
        if not currency_text:
            return None

        # Normalize to lowercase for matching
        text_lower = currency_text.lower().strip()

        # Check if already an ISO code
        if currency_text.upper() in self.valid_iso_codes:
            return currency_text.upper()

        # Look up in mappings
        mapped = self.currency_mappings.get(text_lower)

        # If no mapping found, return original (might be valid ISO code we don't know)
        return mapped if mapped else currency_text.upper()
