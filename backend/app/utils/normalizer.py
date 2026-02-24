"""
Data normalization utilities for parsing and cleaning extracted data.

This module provides functions to parse and normalize data extracted from documents,
converting strings to appropriate types and handling various formats.
"""

import logging
import re
from datetime import datetime
from typing import Optional
from app.utils.constants import normalize_threshold, THRESHOLD_INFINITY

logger = logging.getLogger(__name__)


def parse_currency(value: str) -> Optional[float]:
    """
    Parse currency string to float.

    Handles various currency formats:
    - "$2,000,000" -> 2000000.0
    - "USD 250,000" -> 250000.0
    - "2000000" -> 2000000.0
    - "Infinity" -> float('inf') (infinite threshold = no margin call ever)
    - "N/A" or "Not Applicable" -> 0.0 (zero threshold = immediate margin call)
    - Empty string -> None

    Business Logic for Thresholds:
    - "Infinity"/"Unlimited" → float('inf'): Party never posts collateral
    - "N/A"/"0" → 0.0: Margin calls trigger on any exposure

    Args:
        value: Currency string to parse

    Returns:
        Parsed float value (can be 0.0, finite number, or inf), or None for empty

    Examples:
        >>> parse_currency("$2,000,000")
        2000000.0
        >>> parse_currency("USD 250,000")
        250000.0
        >>> parse_currency("Infinity")
        inf
        >>> parse_currency("N/A")
        0.0
    """
    if not value:
        return None

    value_str = str(value).strip()

    # Use normalize_threshold for special threshold values
    # This handles "Infinity" → inf and "N/A" → 0.0
    normalized = normalize_threshold(value_str)

    # If normalize_threshold returned a special value (inf or 0 from N/A), use it
    if normalized == THRESHOLD_INFINITY:
        return THRESHOLD_INFINITY
    if value_str.lower() in ["n/a", "none", "not applicable", "na", ""]:
        return 0.0

    try:
        # Try to parse as normal currency value
        # Remove currency symbols and common text
        cleaned = re.sub(r"[^\d.,\-]", "", value_str)
        # Remove commas
        cleaned = cleaned.replace(",", "")
        return float(cleaned) if cleaned else None
    except (ValueError, AttributeError) as e:
        logger.warning(f"Could not parse currency value '{value}': {e}, returning None")
        return None


def parse_percentage(value: str) -> Optional[float]:
    """
    Parse percentage string to decimal.

    Handles various percentage formats:
    - "98%" -> 0.98
    - "95" -> 0.95
    - "100%" -> 1.0

    Args:
        value: Percentage string to parse

    Returns:
        Parsed decimal value (0.0-1.0), or None if parsing fails

    Examples:
        >>> parse_percentage("98%")
        0.98
        >>> parse_percentage("95")
        0.95
        >>> parse_percentage("100%")
        1.0
    """
    if not value:
        return None

    try:
        # Remove % symbol and whitespace
        cleaned = str(value).strip().replace("%", "")
        percentage_value = float(cleaned)

        # Convert to decimal (if it's like 98, convert to 0.98)
        if percentage_value > 1.0:
            return percentage_value / 100.0
        return percentage_value
    except (ValueError, AttributeError) as e:
        logger.warning(f"Could not parse percentage '{value}': {e}")
        return None


def parse_date(value: str) -> Optional[datetime]:
    """
    Parse date string to datetime object.

    Uses python-dateutil for flexible date parsing.

    Args:
        value: Date string to parse

    Returns:
        Parsed datetime object, or None if parsing fails

    Examples:
        >>> parse_date("2024-01-15")
        datetime(2024, 1, 15, 0, 0)
        >>> parse_date("January 15, 2024")
        datetime(2024, 1, 15, 0, 0)
    """
    if not value:
        return None

    try:
        # Use dateutil parser for flexible date parsing
        from dateutil import parser

        return parser.parse(value)
    except Exception as e:
        logger.warning(f"Could not parse date '{value}': {e}")
        return None


def calculate_haircut_from_valuation(valuation_percentage: float) -> float:
    """
    Calculate haircut rate from valuation percentage.

    A valuation percentage of 98% means the collateral is valued at 98% of its
    market value, implying a 2% haircut.

    Args:
        valuation_percentage: Valuation percentage as decimal (0.0-1.0)

    Returns:
        Haircut rate as decimal (0.0-1.0)

    Examples:
        >>> calculate_haircut_from_valuation(0.98)
        0.02
        >>> calculate_haircut_from_valuation(1.0)
        0.0
    """
    if valuation_percentage is None:
        return 0.0

    haircut = max(0.0, 1.0 - valuation_percentage)
    return min(haircut, 1.0)  # Ensure haircut doesn't exceed 100%


def parse_rounding_increment(text: str) -> Optional[float]:
    """
    Parse rounding increment from text description.

    Extracts numeric value from rounding rule text like:
    - "Delivery Amount rounded up... to $10,000" -> 10000.0
    - "nearest integral multiple of $10,000.00" -> 10000.0
    - "rounded to USD 50,000" -> 50000.0

    Args:
        text: Rounding rule text

    Returns:
        Rounding increment as float, or None if cannot be parsed

    Examples:
        >>> parse_rounding_increment("rounded up to $10,000")
        10000.0
        >>> parse_rounding_increment("nearest integral multiple of $10,000.00")
        10000.0
    """
    if not text:
        return None

    # Look for currency amounts in the text
    # Pattern: optional currency symbol + digits with optional commas + optional decimals
    pattern = r"[$£€¥]?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)"

    matches = re.findall(pattern, text)
    if matches:
        # Take the last match (usually the actual rounding amount)
        amount_str = matches[-1].replace(",", "")
        try:
            return float(amount_str)
        except ValueError:
            logger.warning(f"Could not convert rounding amount '{amount_str}' to float")
            return None

    logger.warning(f"Could not extract rounding increment from: '{text}'")
    return None


def normalize_counterparty_name(name: str) -> str:
    """
    Normalize counterparty name for consistency.

    Args:
        name: Raw counterparty name

    Returns:
        Normalized name (trimmed, no extra spaces)

    Examples:
        >>> normalize_counterparty_name("  ABC Bank  ")
        "ABC Bank"
        >>> normalize_counterparty_name("XYZ\\nCorp")
        "XYZ Corp"
    """
    if not name:
        return "Unknown Counterparty"

    # Remove extra whitespace and newlines
    normalized = " ".join(str(name).split())
    return normalized.strip()


def validate_currency_value(
    value: float, field_name: str, allow_zero: bool = True
) -> float:
    """
    Validate a currency value is within acceptable range.

    Args:
        value: Currency value to validate
        field_name: Name of the field (for logging)
        allow_zero: Whether zero is an acceptable value

    Returns:
        Validated value

    Raises:
        ValueError: If value is invalid

    Examples:
        >>> validate_currency_value(1000000, "threshold")
        1000000.0
        >>> validate_currency_value(-1000, "threshold")
        Traceback (most recent call last):
        ...
        ValueError: threshold cannot be negative
    """
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative: {value}")

    if not allow_zero and value == 0:
        logger.warning(f"{field_name} is zero, which may be unusual")

    return value


def validate_percentage(value: Optional[float], field_name: str) -> Optional[float]:
    """
    Validate a percentage value is within valid range (0.0-1.0).

    Args:
        value: Percentage value to validate (as decimal)
        field_name: Name of the field (for logging)

    Returns:
        Validated value or None

    Raises:
        ValueError: If value is out of range

    Examples:
        >>> validate_percentage(0.98, "haircut")
        0.98
        >>> validate_percentage(1.5, "haircut")
        Traceback (most recent call last):
        ...
        ValueError: haircut must be between 0.0 and 1.0
    """
    if value is None:
        return None

    if value < 0.0 or value > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0, got {value}")

    return value
