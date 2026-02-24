"""
TemporalNormalizerAgent - Context-aware time and date normalization.

Implements 4-step reasoning chain:
1. Parse Time Format - Extract time components and timezone hints
2. Access Document Context - Get surrounding text for inference (conditional)
3. Infer Timezone - Determine timezone from hints and context
4. Validate and Flag - Ensure result is valid, flag if ambiguous
"""

import time
import json
import re
import asyncio
from typing import Dict, Any, Optional, List
from dateutil import parser as date_parser

from app.services.agents.base_agent import BaseNormalizerAgent
from app.models.agent_schemas import NormalizedTime, NormalizedDate


class TemporalNormalizerAgent(BaseNormalizerAgent):
    """
    Specialized agent for time and date normalization with timezone inference.

    Capabilities:
    - Parse various time formats (12-hour, 24-hour)
    - Infer timezones from context
    - Access document chunks for disambiguation
    - Handle qualitative times ("close of business")
    """

    def __init__(self, api_key: str):
        super().__init__(api_key)

        # Timezone mappings
        self.timezone_mappings = {
            "new york time": "America/New_York",
            "new york": "America/New_York",
            "ny time": "America/New_York",
            "est": "America/New_York",
            "et": "America/New_York",
            "eastern": "America/New_York",
            "edt": "America/New_York",
            "london time": "Europe/London",
            "london": "Europe/London",
            "gmt": "Europe/London",
            "bst": "Europe/London",
            "greenwich": "Europe/London",
            "tokyo time": "Asia/Tokyo",
            "tokyo": "Asia/Tokyo",
            "jst": "Asia/Tokyo",
            "hong kong time": "Asia/Hong_Kong",
            "hong kong": "Asia/Hong_Kong",
            "hkt": "Asia/Hong_Kong",
        }

    async def normalize(
        self,
        data: Dict[str, Any],
        document_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main normalization entry point for time/date fields.

        Args:
            data: Dict with time/date fields to normalize
            document_context: Optional parsed document for context

        Returns:
            Dict with normalized time/date fields
        """
        start_time = time.time()
        self._clear_reasoning_chain()

        normalized_fields = {}

        # Normalize time fields in parallel
        time_fields = ["notification_time", "valuation_time"]
        time_tasks = []
        time_field_names = []

        for field_name in time_fields:
            if field_name in data and data[field_name]:
                time_tasks.append(
                    self._normalize_time_field(
                        field_name=field_name,
                        raw_value=data[field_name],
                        document_context=document_context
                    )
                )
                time_field_names.append(field_name)

        # Execute time field processing in parallel
        if time_tasks:
            time_results = await asyncio.gather(*time_tasks, return_exceptions=True)
            for field_name, result in zip(time_field_names, time_results):
                if isinstance(result, Exception):
                    print(f"ERROR: Failed to normalize time field {field_name}: {result}")
                else:
                    normalized_fields[field_name] = result

        # Normalize date fields (synchronous, but collect them for consistency)
        date_fields = ["agreement_date", "signature_date"]
        for field_name in date_fields:
            if field_name in data and data[field_name]:
                try:
                    normalized_fields[field_name] = self._normalize_date_field(
                        field_name=field_name,
                        raw_value=data[field_name]
                    )
                except Exception as e:
                    print(f"ERROR: Failed to normalize date field {field_name}: {e}")

        processing_time = time.time() - start_time

        return self._format_result(
            data=normalized_fields,
            processing_time=processing_time
        )

    async def _normalize_time_field(
        self,
        field_name: str,
        raw_value: str,
        document_context: Optional[Dict[str, Any]] = None
    ) -> NormalizedTime:
        """
        Normalize a single time field using 4-step reasoning.

        Args:
            field_name: Name of the field (e.g., "notification_time")
            raw_value: Raw time string
            document_context: Optional parsed document

        Returns:
            NormalizedTime object
        """
        # Step 1: Parse Time Format
        parse_result = await self._step1_parse_time_format(raw_value)

        # Step 2: Access Document Context (if timezone not found and context available)
        context_result = None
        if not parse_result.get("timezone_hint") and document_context:
            context_result = self._step2_access_document_context(
                field_name, raw_value, document_context
            )

        # Step 3: Infer Timezone
        timezone_result = await self._step3_infer_timezone(
            parse_result, context_result
        )

        # Step 4: Validate and Flag
        final_result = self._step4_validate_and_flag(
            field_name, raw_value, parse_result, timezone_result
        )

        return NormalizedTime(**final_result)

    async def _step1_parse_time_format(
        self,
        raw_value: str
    ) -> Dict[str, Any]:
        """
        Step 1: Parse time components and extract timezone hints.

        Extracts:
        - Time (normalized to 24-hour format)
        - Timezone indicators
        - Qualitative descriptions

        Model: Haiku
        """
        step_start = time.time()

        prompt = f"""Parse this time string and extract components.

Time String: "{raw_value}"

Extract:
1. Time in 24-hour format (HH:MM or HH:MM:SS)
2. Any timezone indicators (e.g., "EST", "New York time", "GMT")
3. Qualitative descriptions (e.g., "close of business", "end of day")

Return JSON:
{{
  "time_24h": "13:00",
  "timezone_hint": "New York time" or null,
  "description": "close of business" or null,
  "is_qualitative": false
}}

Examples:
- "1:00 p.m., New York time" → {{"time_24h": "13:00", "timezone_hint": "New York time"}}
- "13:00" → {{"time_24h": "13:00", "timezone_hint": null}}
- "close of business" → {{"time_24h": "17:00", "description": "close of business", "is_qualitative": true}}
"""

        response = await self._call_claude(prompt, model=self.haiku_model)

        step_duration = time.time() - step_start

        self._add_reasoning_step(
            step_number=1,
            step_name="parse_time_format",
            input_data={"raw_value": raw_value},
            output_data=response,
            reasoning="Extracted time components and timezone hints",
            model_used="haiku",
            duration_seconds=step_duration
        )

        return response

    def _step2_access_document_context(
        self,
        field_name: str,
        raw_value: str,
        document_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 2: Access document context to find timezone information.

        Looks for timezone mentions in surrounding text.
        Model: Rule-based (document search)
        """
        step_start = time.time()

        context_chunks = []
        timezone_found = None

        # Search for field in document chunks
        markdown = document_context.get("markdown", "")

        # Look for timezone mentions near the time value
        # Search for common timezone patterns in surrounding text
        patterns = [
            r"New York time",
            r"EST",
            r"ET\b",
            r"EDT",
            r"London time",
            r"GMT",
            r"BST",
            r"Tokyo time",
            r"JST",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, markdown, re.IGNORECASE)
            for match in matches:
                # Get surrounding context (100 chars before and after)
                start = max(0, match.start() - 100)
                end = min(len(markdown), match.end() + 100)
                context_text = markdown[start:end]

                # Check if this context mentions the raw time value
                if raw_value[:5] in context_text:  # First 5 chars of time
                    timezone_found = match.group()
                    context_chunks.append({
                        "text": context_text,
                        "timezone_mention": timezone_found
                    })
                    break

            if timezone_found:
                break

        step_duration = time.time() - step_start

        result = {
            "context_accessed": True,
            "chunks_found": len(context_chunks),
            "timezone_found": timezone_found,
            "context_chunks": context_chunks
        }

        self._add_reasoning_step(
            step_number=2,
            step_name="access_document_context",
            input_data={"field_name": field_name},
            output_data=result,
            reasoning=f"Searched document context, found timezone: {timezone_found}" if timezone_found else "Searched document context, no timezone found",
            model_used="rule-based",
            duration_seconds=step_duration
        )

        return result

    async def _step3_infer_timezone(
        self,
        parse_result: Dict[str, Any],
        context_result: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Step 3: Infer timezone from hints and context.

        Uses:
        - Explicit timezone hints from parsing
        - Timezone found in document context
        - Heuristics based on conventions

        Model: Haiku (or Sonnet if ambiguous)
        """
        step_start = time.time()

        timezone_hint = parse_result.get("timezone_hint")
        context_timezone = None
        if context_result:
            context_timezone = context_result.get("timezone_found")

        # Determine timezone
        inferred_timezone = None
        inference_source = None
        confidence = 0.5

        if timezone_hint:
            # Explicit timezone in time string
            inferred_timezone = self._map_timezone(timezone_hint)
            inference_source = "explicit"
            confidence = 0.95
        elif context_timezone:
            # Found in document context
            inferred_timezone = self._map_timezone(context_timezone)
            inference_source = "context"
            confidence = 0.90
        else:
            # No timezone information available
            inferred_timezone = None
            inference_source = "none"
            confidence = 0.50

        step_duration = time.time() - step_start

        result = {
            "timezone": inferred_timezone,
            "inference_source": inference_source,
            "confidence": confidence,
            "reasoning": self._get_timezone_reasoning(timezone_hint, context_timezone, inferred_timezone)
        }

        self._add_reasoning_step(
            step_number=3,
            step_name="infer_timezone",
            input_data={
                "timezone_hint": timezone_hint,
                "context_timezone": context_timezone
            },
            output_data=result,
            reasoning=result["reasoning"],
            model_used="rule-based",
            confidence=confidence,
            duration_seconds=step_duration
        )

        return result

    def _step4_validate_and_flag(
        self,
        field_name: str,
        raw_value: str,
        parse_result: Dict[str, Any],
        timezone_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 4: Validate result and flag for human review if needed.

        Checks:
        - Time is in valid range
        - Timezone is valid
        - Confidence meets threshold

        Model: Rule-based
        """
        step_start = time.time()

        # Check if LLM parsing failed
        if parse_result.get("parsed") is False:
            # LLM failed to parse - return error result
            return {
                "time": None,
                "timezone": None,
                "description": None,
                "raw_value": raw_value,
                "confidence": 0.0,
                "inference_source": "parse_failed",
                "requires_human_review": True,
                "error": "Failed to parse time format from LLM response"
            }

        time_24h = parse_result.get("time_24h") or "00:00"
        timezone = timezone_result.get("timezone")
        confidence = timezone_result.get("confidence", 0.5)
        description = parse_result.get("description")

        # Validate time format
        time_valid = self._validate_time_format(time_24h)

        # Determine if human review needed
        requires_review = confidence < 0.80 or not timezone

        step_duration = time.time() - step_start

        result = {
            "time": time_24h + ":00" if len(time_24h) == 5 else time_24h,
            "timezone": timezone,
            "description": description,
            "raw_value": raw_value,
            "confidence": confidence,
            "inference_source": timezone_result.get("inference_source"),
            "requires_human_review": requires_review
        }

        self._add_reasoning_step(
            step_number=4,
            step_name="validate_and_flag",
            input_data={
                "time": time_24h,
                "timezone": timezone,
                "confidence": confidence
            },
            output_data={
                "valid": time_valid,
                "requires_review": requires_review,
                "final_result": result
            },
            reasoning=f"Validation complete. Time valid: {time_valid}. " +
                      (f"Flagged for review (confidence {confidence:.2f})" if requires_review else "No review needed"),
            model_used="rule-based",
            duration_seconds=step_duration
        )

        return result

    def _normalize_date_field(
        self,
        field_name: str,
        raw_value: str
    ) -> NormalizedDate:
        """
        Normalize a date field using dateutil parser.

        Args:
            field_name: Name of the field
            raw_value: Raw date string

        Returns:
            NormalizedDate object
        """
        try:
            parsed_date = date_parser.parse(raw_value)
            normalized_date = parsed_date.strftime("%Y-%m-%d")

            return NormalizedDate(
                date=normalized_date,
                format_detected="auto",
                raw_value=raw_value,
                confidence=0.95
            )
        except Exception:
            # Failed to parse
            return NormalizedDate(
                date=raw_value,  # Keep as-is
                format_detected="unknown",
                raw_value=raw_value,
                confidence=0.50
            )

    def _map_timezone(self, timezone_hint: str) -> Optional[str]:
        """
        Map timezone hint to IANA timezone name.

        Args:
            timezone_hint: Timezone string from text

        Returns:
            IANA timezone name or None
        """
        if not timezone_hint:
            return None

        # Normalize to lowercase for matching
        hint_lower = timezone_hint.lower().strip()

        return self.timezone_mappings.get(hint_lower)

    def _validate_time_format(self, time_str: str) -> bool:
        """
        Validate time is in correct format and valid range.

        Args:
            time_str: Time string (HH:MM or HH:MM:SS)

        Returns:
            True if valid
        """
        # Check for None or non-string values before calling string methods
        if time_str is None or not isinstance(time_str, str):
            return False

        try:
            parts = time_str.split(":")
            if len(parts) < 2:
                return False

            hour = int(parts[0])
            minute = int(parts[1])

            return 0 <= hour <= 23 and 0 <= minute <= 59
        except (ValueError, IndexError, AttributeError):
            return False

    def _get_timezone_reasoning(
        self,
        timezone_hint: Optional[str],
        context_timezone: Optional[str],
        inferred_timezone: Optional[str]
    ) -> str:
        """Generate reasoning explanation for timezone inference."""
        if timezone_hint:
            return f"Explicitly stated as '{timezone_hint}' in time string"
        elif context_timezone:
            return f"Inferred from document context mention of '{context_timezone}'"
        elif inferred_timezone:
            return f"Inferred as '{inferred_timezone}' from heuristics"
        else:
            return "No timezone information available - flagged for human review"
