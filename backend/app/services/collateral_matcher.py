"""
AI-Powered Collateral Matching Service

Uses LLM to match CSV collateral descriptions to CSA document collateral descriptions
and maturity buckets.
"""

import json
import logging
from typing import List, Optional, Dict, Any

from anthropic import Anthropic

from app.config import settings
from app.models.schemas import ParsedCollateralItem, MatchedCollateralItem, CSATerms

logger = logging.getLogger(__name__)


class CollateralMatcherService:
    """Service for AI-powered matching of collateral descriptions to CSA terms."""

    def __init__(self, anthropic_client: Optional[Anthropic] = None):
        """
        Initialize the collateral matcher service.

        Args:
            anthropic_client: Optional Anthropic client. If not provided,
                            creates one using settings.anthropic_api_key
        """
        self.client = anthropic_client or Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"  # Sonnet 4.5 for accurate matching

    def match_collateral_to_csa(
        self,
        parsed_items: List[ParsedCollateralItem],
        csa_terms: CSATerms
    ) -> List[MatchedCollateralItem]:
        """
        Match parsed CSV collateral items to CSA collateral descriptions.

        Args:
            parsed_items: List of parsed collateral items from CSV
            csa_terms: CSA terms containing eligible collateral

        Returns:
            List of MatchedCollateralItem with AI matching results and haircuts

        Raises:
            ValueError: If inputs are invalid
            Exception: If matching fails
        """
        logger.info(f"Matching {len(parsed_items)} collateral items to CSA terms")

        if not parsed_items:
            return []

        if not csa_terms.eligible_collateral:
            raise ValueError("CSA terms must include eligible collateral")

        try:
            # Build eligible collateral catalog for LLM
            eligible_catalog = self._build_eligible_collateral_catalog(csa_terms)

            logger.info(f"Built catalog with {len(eligible_catalog)} collateral types")
            for idx, cat in enumerate(eligible_catalog[:3]):  # Log first 3 for debugging
                logger.info(f"Catalog item {idx}: {cat['csa_description'][:80]}... | Rating events: {cat['rating_events']}")

            # Build matching prompt
            prompt = self._build_matching_prompt(parsed_items, eligible_catalog)

            # Log prompt excerpt for debugging
            logger.info(f"Prompt length: {len(prompt)} chars")
            logger.info(f"Prompt excerpt: {prompt[:500]}...")

            # Write full prompt to debug file
            import os
            debug_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
            os.makedirs(debug_dir, exist_ok=True)
            with open(os.path.join(debug_dir, 'matcher_debug_prompt.txt'), 'w', encoding='utf-8') as f:
                f.write(prompt)

            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                temperature=0.2,  # Low temperature for consistent matching
                system=self._get_system_prompt(),
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            response_text = response.content[0].text

            # Log response excerpt for debugging
            logger.info(f"LLM response length: {len(response_text)} chars")
            logger.info(f"LLM response excerpt: {response_text[:500]}...")

            # Write full response to debug file
            with open(os.path.join(debug_dir, 'matcher_debug_response.txt'), 'w', encoding='utf-8') as f:
                f.write(response_text)

            # Extract JSON from response
            matches = self._parse_matching_response(response_text, parsed_items)

            # Log confidence scores
            confidences = [m.match_confidence for m in matches]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            logger.info(f"Match confidences - Avg: {avg_conf:.2f}, Min: {min(confidences):.2f}, Max: {max(confidences):.2f}")

            logger.info(f"Successfully matched {len(matches)} collateral items")
            return matches

        except Exception as e:
            logger.error(f"Error matching collateral: {str(e)}")
            # Return items with error warnings rather than failing completely
            return [
                MatchedCollateralItem(
                    csv_row_number=item.csv_row_number,
                    csv_description=item.description,
                    market_value=item.market_value,
                    maturity_min=item.maturity_min,
                    maturity_max=item.maturity_max,
                    currency=item.currency,
                    valuation_scenario=item.valuation_scenario or "No Rating Event",
                    match_confidence=0.0,
                    match_reasoning=f"Matching failed: {str(e)}",
                    warnings=[f"AI matching error: {str(e)}"]
                )
                for item in parsed_items
            ]

    def _build_eligible_collateral_catalog(self, csa_terms: CSATerms) -> List[Dict[str, Any]]:
        """Build a catalog of eligible collateral from CSA terms."""
        from collections import defaultdict

        # Group by (base_description, standardized_type) to merge rating events
        collateral_groups = defaultdict(lambda: {
            "csa_description": None,
            "standardized_type": None,
            "rating_events": [],
            "maturity_buckets": {}
        })

        for nc in csa_terms.eligible_collateral:
            # Each NormalizedCollateral has ONE rating_event (singular)
            rating_event = getattr(nc, 'rating_event', 'No Rating Event')
            base_desc = getattr(nc, 'base_description', 'Unknown')
            std_type = str(nc.standardized_type) if hasattr(nc, 'standardized_type') else 'UNKNOWN'

            # Group key: (base_description, standardized_type)
            key = (base_desc, std_type)
            group = collateral_groups[key]

            # Set description and type
            group["csa_description"] = base_desc
            group["standardized_type"] = std_type

            # Add rating event if not already present
            if rating_event not in group["rating_events"]:
                group["rating_events"].append(rating_event)

            # Get maturity buckets - it's a list directly on the NormalizedCollateral
            maturity_buckets = getattr(nc, 'maturity_buckets', [])

            # Build maturity bucket info for this rating event
            group["maturity_buckets"][rating_event] = [
                {
                    "min_years": bucket.min_years,
                    "max_years": bucket.max_years,
                    "haircut": bucket.haircut,
                    "valuation_percentage": bucket.valuation_percentage
                }
                for bucket in maturity_buckets
            ]

        return list(collateral_groups.values())

    def _build_matching_prompt(
        self,
        parsed_items: List[ParsedCollateralItem],
        eligible_catalog: List[Dict[str, Any]]
    ) -> str:
        """Build the LLM prompt for matching collateral."""
        # Format eligible collateral for prompt
        eligible_text = ""
        for idx, item in enumerate(eligible_catalog, 1):
            eligible_text += f"\n{idx}. \"{item['csa_description']}\"\n"
            eligible_text += f"   Standardized Type: {item['standardized_type']}\n"
            eligible_text += f"   Rating Events: {', '.join(item['rating_events'])}\n"

            # Show maturity buckets for each rating event
            for rating_event, buckets in item['maturity_buckets'].items():
                eligible_text += f"   \n   {rating_event}:\n"
                for bucket in buckets:
                    min_str = f"{bucket['min_years']}" if bucket['min_years'] is not None else "0"
                    max_str = f"{bucket['max_years']}" if bucket['max_years'] is not None else "inf"
                    eligible_text += f"      - Maturity: {min_str} to {max_str} years -> Haircut: {bucket['haircut']*100:.1f}%\n"

        # Format CSV items for prompt
        csv_text = ""
        for item in parsed_items:
            csv_text += f"\nRow {item.csv_row_number}:\n"
            csv_text += f"  Description: \"{item.description}\"\n"
            csv_text += f"  Maturity Range: {item.maturity_display}\n"
            csv_text += f"  Market Value: ${item.market_value:,.2f}\n"
            if item.valuation_scenario:
                csv_text += f"  Valuation Scenario: {item.valuation_scenario}\n"

        prompt = f"""You are matching collateral descriptions and maturity ranges from a CSV import
to the eligible collateral defined in a CSA agreement.

CSA Eligible Collateral:
{eligible_text}

CSV Collateral to Match:
{csv_text}

For each CSV row, match it to the best-fitting CSA collateral description and maturity bucket.
Consider BOTH the collateral description AND the maturity range when matching.

For each CSV row, return a JSON object with:
- csv_row: The row number
- matched_csa_description: The exact CSA collateral description (or null if no match)
- matched_standardized_type: The standardized type (or null)
- matched_maturity_bucket_min: Minimum years of matched bucket (or null)
- matched_maturity_bucket_max: Maximum years of matched bucket (or null)
- confidence: Match confidence from 0.0 to 1.0
- reasoning: Brief explanation of why this match was chosen (1-2 sentences)

If a CSV item spans multiple maturity buckets or doesn't fit any bucket precisely, choose the
most conservative (highest haircut) bucket and note this in the reasoning.

If no good match exists (confidence < 0.5), set matched_csa_description to null and explain
why in the reasoning.

Return ONLY a JSON array with one object per CSV row, in order:
[
  {{"csv_row": 1, "matched_csa_description": "...", ...}},
  {{"csv_row": 2, "matched_csa_description": "...", ...}},
  ...
]
"""

        return prompt

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the matching LLM."""
        return """You are a collateral matching expert specializing in ISDA/CSA agreements.
Your job is to accurately match collateral descriptions from CSV imports to the eligible
collateral types defined in CSA documents.

You must:
1. Match based on both description AND maturity range
2. Consider industry standard naming conventions (e.g., "US Treasury" matches "U.S. Treasury Securities")
3. Be conservative when uncertain - use the highest haircut bucket when ranges overlap
4. Provide clear, concise reasoning for each match
5. Return ONLY valid JSON - no additional text or explanation outside the JSON structure

Return matches with high confidence (>0.8) when descriptions clearly match.
Return lower confidence (0.5-0.8) when matches are uncertain.
Return null matches (confidence < 0.5) when no reasonable match exists."""

    def _parse_matching_response(
        self,
        response_text: str,
        parsed_items: List[ParsedCollateralItem]
    ) -> List[MatchedCollateralItem]:
        """Parse LLM response into MatchedCollateralItem objects."""
        try:
            # Try to extract JSON from response
            # Look for JSON array in the response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1

            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON array found in response")

            json_str = response_text[start_idx:end_idx]
            matches_data = json.loads(json_str)

            if not isinstance(matches_data, list):
                raise ValueError("Expected JSON array in response")

            # Create MatchedCollateralItem objects
            matched_items = []
            for match_data in matches_data:
                csv_row = match_data.get('csv_row')

                # Find corresponding parsed item
                parsed_item = next(
                    (item for item in parsed_items if item.csv_row_number == csv_row),
                    None
                )

                if not parsed_item:
                    logger.warning(f"No parsed item found for row {csv_row}")
                    continue

                matched_item = MatchedCollateralItem(
                    csv_row_number=csv_row,
                    csv_description=parsed_item.description,
                    market_value=parsed_item.market_value,
                    maturity_min=parsed_item.maturity_min,
                    maturity_max=parsed_item.maturity_max,
                    currency=parsed_item.currency,
                    valuation_scenario=parsed_item.valuation_scenario or "No Rating Event",
                    matched_csa_description=match_data.get('matched_csa_description'),
                    matched_standardized_type=match_data.get('matched_standardized_type'),
                    matched_maturity_bucket_min=match_data.get('matched_maturity_bucket_min'),
                    matched_maturity_bucket_max=match_data.get('matched_maturity_bucket_max'),
                    match_confidence=match_data.get('confidence', 0.0),
                    match_reasoning=match_data.get('reasoning', ''),
                    warnings=[]
                )

                # Add low confidence warning
                if matched_item.match_confidence < 0.7:
                    matched_item.warnings.append(
                        f"Low confidence match ({matched_item.match_confidence:.0%})"
                    )

                matched_items.append(matched_item)

            return matched_items

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.error(f"Response text: {response_text}")
            raise ValueError(f"Invalid JSON in LLM response: {str(e)}")
        except Exception as e:
            logger.error(f"Error parsing matching response: {str(e)}")
            raise
