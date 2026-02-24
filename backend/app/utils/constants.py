"""
Constants and utility functions for CSA Margin Manager
"""

from math import inf
from typing import Union

# Special threshold values
THRESHOLD_INFINITY = inf  # Represents infinite threshold (no margin call ever)
THRESHOLD_ZERO = 0.0  # Represents zero threshold (immediate margin call)

# String representations that should be treated as infinity
INFINITY_STRINGS = ["infinity", "inf", "∞", "unlimited", "none", "null"]

# String representations that should be treated as zero
ZERO_STRINGS = ["n/a", "na", "0", "zero", ""]


def normalize_threshold(value: Union[str, float, int, None]) -> float:
    """
    Normalize threshold values from various representations to proper numeric values.

    Business Logic:
    - "Infinity" / "Unlimited" → float('inf') - No margin call ever triggered for that party
    - "N/A" / "0" → 0.0 - Margin call triggers on any exposure
    - Numeric values → converted to float

    Args:
        value: Threshold value from CSA document (can be string, number, or None)

    Returns:
        float: Normalized threshold value (0.0, finite number, or inf)

    Examples:
        >>> normalize_threshold("Infinity")
        inf
        >>> normalize_threshold("N/A")
        0.0
        >>> normalize_threshold("1000000")
        1000000.0
        >>> normalize_threshold(None)
        0.0
    """
    # Handle None
    if value is None:
        return THRESHOLD_ZERO

    # Already a number
    if isinstance(value, (int, float)):
        # Check if it's already infinity
        if value == inf or value == float('inf'):
            return THRESHOLD_INFINITY
        return float(value)

    # Convert to string and normalize
    value_str = str(value).lower().strip()

    # Check if string STARTS WITH infinity keywords (handles "Infinity; provided that..." cases)
    if any(value_str.startswith(inf_str) for inf_str in INFINITY_STRINGS):
        return THRESHOLD_INFINITY

    # Check for exact infinity match
    if value_str in INFINITY_STRINGS:
        return THRESHOLD_INFINITY

    # Check for zero representations
    if value_str in ZERO_STRINGS:
        return THRESHOLD_ZERO

    # Try to parse as number
    try:
        parsed = float(value_str)
        # Check if parsed value is infinity
        if parsed == inf or parsed == float('inf'):
            return THRESHOLD_INFINITY
        return parsed
    except (ValueError, TypeError):
        # If unparseable, default to zero (safest for margin calls)
        return THRESHOLD_ZERO


def is_infinite_threshold(value: float) -> bool:
    """
    Check if a threshold value represents infinity.

    Args:
        value: Threshold value to check

    Returns:
        bool: True if threshold is infinite, False otherwise
    """
    return value == inf or value == float('inf')


def format_threshold_value(value: float) -> str:
    """
    Format threshold value for display or serialization.

    Args:
        value: Threshold value

    Returns:
        str: Formatted string representation
    """
    if is_infinite_threshold(value):
        return "Infinity"
    return str(value)
