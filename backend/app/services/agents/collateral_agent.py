"""
CollateralNormalizerAgent - Deep 6-step reasoning for collateral normalization.

Implements multi-step reasoning chain:
1. Initial Parse - Extract basic structure
2. Detect Ambiguities - Find unclear elements
3. Resolve Ambiguities - Apply domain knowledge (conditional)
4. Validate Taxonomy - Check against valid types
5. Validate Logic - Check consistency and ranges
6. Synthesize - Produce final high-confidence output
"""

import time
import json
import asyncio
from typing import Dict, Any, Optional, List
from difflib import get_close_matches

from app.services.agents.base_agent import BaseNormalizerAgent
from app.models.normalized_collateral import (
    StandardizedCollateralType,
    NormalizedCollateral,
    MaturityBucket,
)
from app.models.agent_schemas import (
    Ambiguity,
    AmbiguityDetection,
    AmbiguitySeverity,
    Resolution,
    AmbiguityResolution,
    ValidationResult,
    Correction,
)


class CollateralNormalizerAgent(BaseNormalizerAgent):
    """
    Specialized agent for collateral normalization using 6-step reasoning.

    Provides:
    - Deep multi-step reasoning
    - Ambiguity detection and resolution
    - Self-correction via validation
    - Full reasoning transparency
    """

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.valid_types = [t.value for t in StandardizedCollateralType]

    async def normalize(
        self,
        data: Dict[str, Any],
        document_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main normalization entry point with adaptive batching for large documents.

        Args:
            data: Dict with collateral_type, valuation_string, rating_event
            document_context: Optional parsed document for context

        Returns:
            Dict with normalized collateral items and reasoning
        """
        start_time = time.time()
        self._clear_reasoning_chain()

        collateral_items = data.get("collateral_items", [])

        # Process all items in parallel with adaptive batching
        if collateral_items:
            # Import config for dynamic batching settings
            try:
                from app.config import settings
                auto_batch = len(collateral_items) > settings.auto_batch_threshold
                batch_size = settings.parallel_batch_size if auto_batch else len(collateral_items)
            except (ImportError, AttributeError):
                # Fallback: no batching
                auto_batch = False
                batch_size = len(collateral_items)

            normalized_items = []

            if auto_batch:
                print(f"Large document detected ({len(collateral_items)} items). Using adaptive batching with batch_size={batch_size}")

            # Process items in batches
            for batch_start in range(0, len(collateral_items), batch_size):
                batch_end = min(batch_start + batch_size, len(collateral_items))
                batch_items = collateral_items[batch_start:batch_end]

                if auto_batch:
                    print(f"Processing batch {batch_start//batch_size + 1}: items {batch_start+1}-{batch_end}")

                # Create tasks for this batch
                tasks = [
                    self._normalize_single_item(
                        collateral_type=item.get("collateral_type", ""),
                        valuation_string=item.get("valuation_string", ""),
                        rating_event=item.get("rating_event", ""),
                        rating_event_order=item.get("rating_event_order", batch_start + idx),
                        document_context=document_context
                    )
                    for idx, item in enumerate(batch_items)
                ]

                # Execute batch in parallel with error handling
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Filter successful results and log errors
                for idx, result in enumerate(results):
                    item_index = batch_start + idx
                    if isinstance(result, Exception):
                        print(f"ERROR: Failed to normalize collateral item {item_index}: {result}")
                        # Add error placeholder to maintain item count
                        normalized_items.append({
                            "error": str(result),
                            "item_index": item_index,
                            "raw_data": batch_items[idx]
                        })
                    else:
                        normalized_items.append(result)
        else:
            normalized_items = []

        processing_time = time.time() - start_time

        return self._format_result(
            data={"normalized_items": normalized_items},
            processing_time=processing_time
        )

    async def _normalize_single_item(
        self,
        collateral_type: str,
        valuation_string: str,
        rating_event: str,
        rating_event_order: int = 0,
        document_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Normalize a single collateral item using 6-step reasoning.

        Args:
            collateral_type: Raw collateral type description
            valuation_string: Valuation percentage string with optional maturity buckets
            rating_event: Rating event this applies to
            rating_event_order: Position of rating event in column order
            document_context: Optional parsed document

        Returns:
            Normalized collateral dict with reasoning chain
        """
        # Step 1: Initial Parse
        parse_result = await self._step1_initial_parse(
            collateral_type, valuation_string, rating_event
        )

        # Step 2: Detect Ambiguities
        ambiguity_detection = await self._step2_detect_ambiguities(
            parse_result, valuation_string
        )

        # Step 3: Resolve Ambiguities (conditional - only if needed)
        if ambiguity_detection.needs_resolution:
            resolution = await self._step3_resolve_ambiguities(
                parse_result, ambiguity_detection, valuation_string, document_context
            )
            # Apply resolutions to parse_result
            parse_result = self._apply_resolutions(parse_result, resolution)

        # Step 4: Validate Taxonomy
        taxonomy_validation = self._step4_validate_taxonomy(parse_result)

        # Self-correction if taxonomy invalid
        if not taxonomy_validation.passed:
            parse_result = self._apply_taxonomy_corrections(
                parse_result, taxonomy_validation
            )

        # Step 5: Validate Logic
        logic_validation = self._step5_validate_logic(parse_result)

        # Self-correction if logic invalid
        if not logic_validation.passed:
            parse_result = self._apply_logic_corrections(
                parse_result, logic_validation
            )

        # Step 6: Synthesize
        final_result = await self._step6_synthesize(parse_result, rating_event, rating_event_order)

        # Preserve original collateral_type for base_description
        final_result["collateral_type"] = collateral_type

        return final_result

    async def _step1_initial_parse(
        self,
        collateral_type: str,
        valuation_string: str,
        rating_event: str
    ) -> Dict[str, Any]:
        """
        Step 1: Initial structural parsing.

        Focus: Extract basic structure without worrying about ambiguities.
        Model: Haiku (fast, cost-effective)
        """
        step_start = time.time()

        prompt = f"""Parse this collateral entry to extract maturity information from BOTH the collateral type and valuation string fields.

Collateral Type: {collateral_type}
Valuation String: {valuation_string}
Rating Event: {rating_event}

Extract:
1. Standardized collateral type from this list:
   {', '.join(self.valid_types)}
2. Maturity information from BOTH fields (collateral_type AND valuation_string)
3. Haircut percentages for each bucket

Think step-by-step about what you see in BOTH fields.

ANALYZE BOTH FIELDS FOR MATURITY INFORMATION:

STEP 1 - Check collateral_type field for maturity phrases like:
- "having a remaining maturity of up to and not more than X year" -> (null, X)
- "remaining maturity of greater than X year but not more than Y years" -> (X, Y)
- "remaining maturity of greater than X years" -> (X, null)
- "remaining maturity of not more than X days" -> (null, X/365)
- "maturity of X to Y years" -> (X, Y)
- "(1-5yr)" or similar notation in parentheses

STEP 2 - Check valuation_string field for maturity buckets:
- "99% (1-2yr)" format means 99% valuation for 1 to 2 year maturity
- Format like "(1-2yr)" means minimum 1 year, maximum 2 years
- Format like ">20yr" means minimum 20 years, no maximum (use null)
- Format like "<1yr" means no minimum (use null), maximum 1 year

STEP 3 - Merge maturity information:
- If maturity is ONLY in collateral_type: Create a single bucket with that range and the percentage from valuation_string
- If maturity is ONLY in valuation_string: Use those buckets (current behavior)
- If maturity is in BOTH fields: Use valuation_string buckets (more granular) and store collateral_type maturity separately
- If NO maturity in either field: Use a single bucket with min_years=null and max_years=null

IMPORTANT RULES:
- IF NO MATURITY IS MENTIONED IN EITHER FIELD: Use a single bucket with min_years=null and max_years=null
- Some entries have no maturity buckets (e.g., cash) - just a single percentage which means all maturities
- Convert days to years by dividing by 365 (e.g., "30 days" becomes 0.082 years)

EDGE CASE HANDLING:
- If collateral type cannot be confidently mapped to the standardized list, use "UNKNOWN"
- If valuation percentages cannot be determined (e.g., "% to be determined", "TBD"), set maturity_buckets to empty array []
- For "Other" or catch-all categories that don't match standardized types, use "UNKNOWN"

Return JSON with this structure:
{{
  "standardized_type": "US_TREASURY",
  "maturity_from_collateral_type": {{
    "min_years": 1.0,
    "max_years": 5.0,
    "source_text": "having a remaining maturity of 1 to 5 years"
  }},
  "maturity_buckets": [
    {{
      "min_maturity_years": 1.0,
      "max_maturity_years": 2.0,
      "valuation_percentage": 99.0,
      "haircut_percentage": 1.0,
      "source": "valuation_string"
    }}
  ]
}}

NOTE: If no maturity is found in collateral_type, set maturity_from_collateral_type to null.
If maturity buckets have explicit ranges, set source to "valuation_string".
If created from collateral_type maturity, set source to "collateral_type".
"""

        response = await self._call_claude(prompt, model=self.haiku_model)

        step_duration = time.time() - step_start

        self._add_reasoning_step(
            step_number=1,
            step_name="initial_parse",
            input_data={
                "collateral_type": collateral_type,
                "valuation_string": valuation_string,
                "rating_event": rating_event
            },
            output_data=response,
            reasoning="Initial structural extraction from raw text",
            model_used="haiku",
            duration_seconds=step_duration
        )

        return response

    async def _step2_detect_ambiguities(
        self,
        parse_result: Dict[str, Any],
        original_string: str
    ) -> AmbiguityDetection:
        """
        Step 2: Identify ambiguous or unclear elements.

        Common ambiguities:
        - Unclear maturity boundaries (inclusive/exclusive)
        - Overlapping buckets
        - Missing information
        - Inconsistent formats

        Model: Haiku
        """
        step_start = time.time()

        prompt = f"""Review this parsed result and identify any ambiguities or uncertainties, including maturity conflicts.

Original String: {original_string}
Parsed Result: {json.dumps(parse_result, indent=2)}

Are there any elements that are:
1. Ambiguous (could be interpreted multiple ways)
2. Unclear (missing information)
3. Potentially incorrect
4. Inconsistent

IMPORTANT - Check for maturity conflicts:
5. If both "maturity_from_collateral_type" and "maturity_buckets" exist, check if they conflict:
   - Do the maturity buckets fall within the collateral_type maturity range?
   - Example conflict: collateral_type says "1-5 years" but bucket says "5-10yr"
   - Example consistent: collateral_type says "1-5 years" and buckets are "1-2yr, 2-3yr, 3-5yr"
6. Mark conflicts as HIGH severity if maturity ranges don't overlap at all
7. Mark as MEDIUM severity if buckets partially exceed the collateral_type range

For each ambiguity found, specify:
- issue: Description of the ambiguity
- severity: "high", "medium", or "low"
- field: Which field is affected
- suggested_resolution: (optional) How to resolve this

Return JSON:
{{
  "ambiguities": [
    {{"issue": "...", "severity": "low", "field": "...", "suggested_resolution": "..."}}
  ],
  "needs_context": false,
  "needs_resolution": true
}}
"""

        response = await self._call_claude(prompt, model=self.haiku_model)

        step_duration = time.time() - step_start

        # Parse ambiguities into structured format
        ambiguities = []
        for amb in response.get("ambiguities", []):
            ambiguities.append(Ambiguity(
                issue=amb.get("issue", ""),
                severity=AmbiguitySeverity(amb.get("severity", "low")),
                field=amb.get("field", ""),
                suggested_resolution=amb.get("suggested_resolution")
            ))

        detection = AmbiguityDetection(
            ambiguities=ambiguities,
            needs_context=response.get("needs_context", False),
            needs_resolution=response.get("needs_resolution", False),
            reasoning=response.get("reasoning", "Ambiguity detection completed")
        )

        self._add_reasoning_step(
            step_number=2,
            step_name="detect_ambiguities",
            input_data={"parse_result": parse_result},
            output_data={
                "ambiguities_count": len(ambiguities),
                "needs_resolution": detection.needs_resolution,
                "ambiguities": [amb.dict() for amb in ambiguities]
            },
            reasoning=detection.reasoning,
            model_used="haiku",
            duration_seconds=step_duration
        )

        return detection

    async def _step3_resolve_ambiguities(
        self,
        parse_result: Dict[str, Any],
        ambiguities: AmbiguityDetection,
        original_string: str,
        context: Optional[Dict[str, Any]]
    ) -> AmbiguityResolution:
        """
        Step 3: Resolve identified ambiguities using domain knowledge.

        Applies CSA conventions and accesses document context if needed.
        Model: Sonnet (better reasoning)
        """
        step_start = time.time()

        context_str = ""
        if context:
            context_str = f"\nDocument Context Available: Yes"

        prompt = f"""Resolve these ambiguities using domain knowledge about CSA agreements, including maturity conflicts.

Original String: {original_string}
Current Parse: {json.dumps(parse_result, indent=2)}
Ambiguities: {json.dumps([amb.dict() for amb in ambiguities.ambiguities], indent=2)}
{context_str}

For each ambiguity, provide:
1. Your interpretation
2. Reasoning based on CSA conventions
3. Confidence level (0.0-1.0)
4. Sources used (e.g., "csa_convention", "document_context", "domain_knowledge")

Apply these domain rules:
- Maturity buckets in CSAs typically use "X-Y yr" format meaning "X to Y years"
- Upper bounds are typically EXCLUSIVE (1-2yr means [1.0, 2.0) years)
- Haircuts decrease (percentages increase) as maturity increases for same security type
- Overlapping buckets for a single collateral are rare and usually errors
- "Infinity" or ">Xyr" means no upper maturity limit (null)

MATURITY CONFLICT RESOLUTION RULES:
When maturity appears in both collateral_type and valuation_string:
1. If valuation_string has bucketed percentages (e.g., "99% (1-2yr), 98% (2-3yr)"):
   - Use valuation_string buckets (more granular and specific)
   - Validate that buckets fall within collateral_type maturity bounds
   - If buckets exceed collateral_type bounds: Flag as error but prefer valuation_string (it's actual pricing data)

2. If maturity ONLY in collateral_type and valuation_string has single percentage:
   - Create a single bucket using collateral_type maturity range

3. If maturities CONFLICT (no overlap):
   - Prefer valuation_string if it has explicit maturity buckets
   - Flag as HIGH confidence issue for human review
   - Document the conflict in reasoning

4. If maturity CONSISTENT (buckets within collateral_type range):
   - Use valuation_string buckets as-is
   - Note consistency in reasoning

Return JSON:
{{
  "resolutions": [
    {{
      "ambiguity": "description",
      "interpretation": "your interpretation",
      "reasoning": "why this interpretation",
      "confidence": 0.95,
      "sources_used": ["csa_convention"]
    }}
  ]
}}
"""

        response = await self._call_claude(prompt, model=self.sonnet_model)

        step_duration = time.time() - step_start

        # Parse resolutions
        resolutions = []
        for res in response.get("resolutions", []):
            resolutions.append(Resolution(
                ambiguity=res.get("ambiguity", ""),
                interpretation=res.get("interpretation", ""),
                reasoning=res.get("reasoning", ""),
                confidence=res.get("confidence", 0.8),
                sources_used=res.get("sources_used", ["domain_knowledge"])
            ))

        resolution = AmbiguityResolution(
            resolutions=resolutions,
            model_used="sonnet"
        )

        self._add_reasoning_step(
            step_number=3,
            step_name="resolve_ambiguities",
            input_data={"ambiguities": [amb.dict() for amb in ambiguities.ambiguities]},
            output_data={"resolutions": [res.dict() for res in resolutions]},
            reasoning="Applied domain knowledge to resolve ambiguities",
            model_used="sonnet",
            confidence=sum(r.confidence for r in resolutions) / len(resolutions) if resolutions else 0.8,
            duration_seconds=step_duration
        )

        return resolution

    def _step4_validate_taxonomy(
        self,
        parse_result: Dict[str, Any]
    ) -> ValidationResult:
        """
        Step 4: Validate against known collateral taxonomy.

        Checks if standardized_type exists in valid types enum.
        Model: Rule-based
        """
        step_start = time.time()

        extracted_type = parse_result.get("standardized_type", "")
        is_valid = extracted_type in self.valid_types

        issues = []
        corrections = []
        suggestions = []

        if not is_valid:
            issues.append(f"Invalid collateral type: '{extracted_type}'")

            # Find closest match
            close_matches = get_close_matches(
                extracted_type,
                self.valid_types,
                n=3,
                cutoff=0.6
            )
            if close_matches:
                suggestions.append(f"Did you mean one of: {', '.join(close_matches)}")

        step_duration = time.time() - step_start

        result = ValidationResult(
            step_number=4,
            passed=is_valid,
            issues=issues,
            corrections=corrections,
            suggestions=suggestions,
            reasoning="Validated collateral type against StandardizedCollateralType taxonomy"
        )

        self._add_reasoning_step(
            step_number=4,
            step_name="validate_taxonomy",
            input_data={"standardized_type": extracted_type},
            output_data={
                "passed": is_valid,
                "valid_type": extracted_type if is_valid else None,
                "suggestions": suggestions
            },
            reasoning=result.reasoning,
            model_used="rule-based",
            duration_seconds=step_duration
        )

        return result

    def _step5_validate_logic(
        self,
        parse_result: Dict[str, Any]
    ) -> ValidationResult:
        """
        Step 5: Validate logical consistency.

        Checks:
        - No overlapping maturity buckets
        - Haircuts in valid range (0-100%)
        - Maturity ranges make sense (min < max)
        - Percentages generally increase with maturity

        Model: Rule-based
        """
        step_start = time.time()

        buckets = parse_result.get("maturity_buckets", [])
        issues = []
        corrections = []

        # Check for overlapping buckets
        for i, bucket1 in enumerate(buckets):
            for j, bucket2 in enumerate(buckets[i+1:], start=i+1):
                if self._buckets_overlap(bucket1, bucket2):
                    issues.append(
                        f"Overlapping buckets: bucket {i} ({bucket1.get('min_maturity_years')}-"
                        f"{bucket1.get('max_maturity_years')}yr) and bucket {j} "
                        f"({bucket2.get('min_maturity_years')}-{bucket2.get('max_maturity_years')}yr)"
                    )

        # Check haircut values (handle None gracefully for unparseable values)
        for i, bucket in enumerate(buckets):
            haircut = bucket.get("haircut_percentage", 0)
            valuation = bucket.get("valuation_percentage", 0)

            # Only validate if not None (None is valid for unparseable items like "% to be determined")
            if haircut is not None and (haircut < 0 or haircut > 100):
                issues.append(f"Invalid haircut {haircut}% for bucket {i}")

            if valuation is not None and (valuation < 0 or valuation > 100):
                issues.append(f"Invalid valuation {valuation}% for bucket {i}")

        # Check maturity ordering
        for i, bucket in enumerate(buckets):
            min_yr = bucket.get("min_maturity_years")
            max_yr = bucket.get("max_maturity_years")

            if min_yr is not None and max_yr is not None:
                try:
                    min_yr = float(min_yr)
                    max_yr = float(max_yr)
                    if min_yr >= max_yr:
                        issues.append(
                            f"Invalid maturity range for bucket {i}: min ({min_yr}) >= max ({max_yr})"
                        )
                except (TypeError, ValueError):
                    issues.append(
                        f"Invalid maturity values for bucket {i}: min={min_yr}, max={max_yr} (not numeric)"
                    )

        # Check for maturity consistency between collateral_type and buckets
        maturity_from_type = parse_result.get("maturity_from_collateral_type")
        if maturity_from_type:
            type_min = maturity_from_type.get("min_years")
            type_max = maturity_from_type.get("max_years")

            # Only validate if collateral_type has defined bounds
            if type_min is not None or type_max is not None:
                for i, bucket in enumerate(buckets):
                    bucket_min = bucket.get("min_maturity_years")
                    bucket_max = bucket.get("max_maturity_years")

                    # Skip validation for buckets with null bounds (apply to all maturities)
                    if bucket_min is None and bucket_max is None:
                        continue

                    try:
                        # Check if bucket falls outside collateral_type range
                        if type_min is not None and bucket_min is not None:
                            if float(bucket_min) < float(type_min):
                                issues.append(
                                    f"Maturity conflict in bucket {i}: bucket min ({bucket_min} years) "
                                    f"is less than collateral_type min ({type_min} years). "
                                    f"Source: {maturity_from_type.get('source_text', 'N/A')}"
                                )

                        if type_max is not None and bucket_max is not None:
                            if float(bucket_max) > float(type_max):
                                issues.append(
                                    f"Maturity conflict in bucket {i}: bucket max ({bucket_max} years) "
                                    f"exceeds collateral_type max ({type_max} years). "
                                    f"Source: {maturity_from_type.get('source_text', 'N/A')}"
                                )
                    except (TypeError, ValueError):
                        # If conversion fails, skip this validation
                        pass

        # Check for unusual maturity values
        for i, bucket in enumerate(buckets):
            min_yr = bucket.get("min_maturity_years")
            max_yr = bucket.get("max_maturity_years")

            # Flag very small maturity values (< 0.1 years = 36.5 days)
            if max_yr is not None:
                try:
                    max_val = float(max_yr)
                    if max_val < 0.1:
                        days = int(max_val * 365)
                        issues.append(
                            f"Unusual maturity value for bucket {i}: max={max_val} years "
                            f"(~{days} days). Verify this is correct."
                        )
                except (TypeError, ValueError):
                    pass

            # Flag oddly precise values (more than 2 decimal places)
            if min_yr is not None:
                try:
                    min_val = float(min_yr)
                    min_str = f"{min_val:.10f}".rstrip('0').rstrip('.')
                    if '.' in min_str and len(min_str.split('.')[1]) > 2:
                        issues.append(
                            f"Unusually precise maturity value for bucket {i}: min={min_val} years. "
                            f"Consider rounding to 2 decimal places."
                        )
                except (TypeError, ValueError):
                    pass

            if max_yr is not None:
                try:
                    max_val = float(max_yr)
                    max_str = f"{max_val:.10f}".rstrip('0').rstrip('.')
                    if '.' in max_str and len(max_str.split('.')[1]) > 2:
                        issues.append(
                            f"Unusually precise maturity value for bucket {i}: max={max_val} years. "
                            f"Consider rounding to 2 decimal places."
                        )
                except (TypeError, ValueError):
                    pass

        # Check for potential maturity bucket gaps
        sorted_buckets = sorted(
            [b for b in buckets if b.get("min_maturity_years") is not None],
            key=lambda b: float(b.get("min_maturity_years", 0))
        )
        for i in range(len(sorted_buckets) - 1):
            current_max = sorted_buckets[i].get("max_maturity_years")
            next_min = sorted_buckets[i+1].get("min_maturity_years")

            if current_max is not None and next_min is not None:
                try:
                    current_max_val = float(current_max)
                    next_min_val = float(next_min)
                    gap = next_min_val - current_max_val
                    if gap > 0.01:  # Gap larger than ~3.65 days
                        issues.append(
                            f"Maturity bucket gap detected: bucket {i} ends at {current_max_val} years, "
                            f"but bucket {i+1} starts at {next_min_val} years (gap: {gap:.3f} years). "
                            f"Verify this gap is intentional."
                        )
                except (TypeError, ValueError):
                    pass

        step_duration = time.time() - step_start

        result = ValidationResult(
            step_number=5,
            passed=len(issues) == 0,
            issues=issues,
            corrections=corrections,
            suggestions=[],
            reasoning="Validated logical consistency of parsed data"
        )

        self._add_reasoning_step(
            step_number=5,
            step_name="validate_logic",
            input_data={"buckets_count": len(buckets)},
            output_data={
                "passed": result.passed,
                "issues_count": len(issues),
                "issues": issues
            },
            reasoning=result.reasoning,
            model_used="rule-based",
            duration_seconds=step_duration
        )

        return result

    async def _step6_synthesize(
        self,
        parse_result: Dict[str, Any],
        rating_event: str = "",
        rating_event_order: int = 0
    ) -> Dict[str, Any]:
        """
        Step 6: Synthesize final high-confidence result.

        Reviews complete reasoning chain and produces final output with confidence.
        Model: Sonnet
        """
        step_start = time.time()

        # Review reasoning chain
        reasoning_summary = [
            {
                "step": step.step_number,
                "name": step.step_name,
                "model": step.model_used,
                "confidence": step.confidence
            }
            for step in self.reasoning_chain
        ]

        prompt = f"""Synthesize the final normalized collateral output.

Parsed Data: {json.dumps(parse_result, indent=2)}

Reasoning Chain Summary:
{json.dumps(reasoning_summary, indent=2)}

Produce:
1. Final confidence score (0.0-1.0) considering:
   - Quality of initial parse
   - Number of ambiguities resolved
   - Validation results
   - Number of self-corrections needed
2. Summary of key decisions made
3. Final validated output

Return JSON:
{{
  "final_data": {{...parsed data...}},
  "confidence": 0.97,
  "summary": "Brief summary of processing"
}}
"""

        response = await self._call_claude(prompt, model=self.sonnet_model)

        step_duration = time.time() - step_start

        # Extract metadata fields from response
        confidence = response.get("confidence", 0.85)
        summary = response.get("summary", "Synthesis completed")

        # Get final data - if response has final_data, use it; otherwise use parse_result
        # If response parsing failed, it will have 'parsed': False, so use parse_result
        if response.get("parsed") is False or "final_data" not in response:
            final_data = parse_result
        else:
            final_data = response.get("final_data", parse_result)

        self._add_reasoning_step(
            step_number=6,
            step_name="synthesize",
            input_data={"reasoning_chain_length": len(self.reasoning_chain)},
            output_data={
                "confidence": confidence,
                "summary": summary
            },
            reasoning=summary,
            model_used="sonnet",
            confidence=confidence,
            duration_seconds=step_duration
        )

        # Defensive fallback: Ensure standardized_type exists (default to UNKNOWN if missing)
        if "standardized_type" not in final_data or not final_data["standardized_type"]:
            final_data["standardized_type"] = "UNKNOWN"
            # Reduce confidence for items that couldn't be classified
            confidence = min(confidence, 0.5)

        return {
            **final_data,
            "confidence": confidence,
            "summary": summary,
            "rating_event": rating_event,
            "rating_event_order": rating_event_order
        }

    def _buckets_overlap(self, bucket1: Dict, bucket2: Dict) -> bool:
        """Check if two maturity buckets overlap."""
        min1 = bucket1.get("min_maturity_years")
        max1 = bucket1.get("max_maturity_years")
        min2 = bucket2.get("min_maturity_years")
        max2 = bucket2.get("max_maturity_years")

        # If either bucket has null bounds, can't determine overlap (applies to all)
        if None in [min1, max1, min2, max2]:
            return False

        # Validate types before comparison to prevent TypeError
        try:
            min1 = float(min1)
            max1 = float(max1)
            min2 = float(min2)
            max2 = float(max2)
        except (TypeError, ValueError):
            # If conversion fails, can't compare - treat as non-overlapping
            return False

        # Check for overlap: buckets overlap if one starts before the other ends
        return not (max1 <= min2 or max2 <= min1)

    def _apply_resolutions(
        self,
        parse_result: Dict[str, Any],
        resolution: AmbiguityResolution
    ) -> Dict[str, Any]:
        """Apply ambiguity resolutions to parse result."""
        # For now, return as-is
        # In production, would apply specific resolutions based on field
        return parse_result

    def _apply_taxonomy_corrections(
        self,
        parse_result: Dict[str, Any],
        validation: ValidationResult
    ) -> Dict[str, Any]:
        """Apply taxonomy corrections if type is invalid."""
        if validation.suggestions:
            # Extract first suggestion
            suggestion_text = validation.suggestions[0]
            if "Did you mean one of:" in suggestion_text:
                # Get first suggested type
                suggested_types = suggestion_text.split(": ")[1].split(", ")
                if suggested_types:
                    corrected_type = suggested_types[0]
                    parse_result["standardized_type"] = corrected_type

                    # Log correction in validation result
                    validation.corrections.append(Correction(
                        correction_type="taxonomy",
                        original_value=parse_result.get("standardized_type"),
                        corrected_value=corrected_type,
                        reasoning=f"Corrected invalid type to closest match: {corrected_type}",
                        confidence=0.7
                    ))

        return parse_result

    def _apply_logic_corrections(
        self,
        parse_result: Dict[str, Any],
        validation: ValidationResult
    ) -> Dict[str, Any]:
        """Apply logic corrections if validation failed."""
        # For now, return as-is
        # In production, would fix overlapping buckets, clamp invalid percentages, etc.
        return parse_result
