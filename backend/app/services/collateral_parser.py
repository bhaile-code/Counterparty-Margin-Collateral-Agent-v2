"""
CSV Collateral Parser Service

Parses and validates CSV files containing collateral data with maturity ranges.
Supports maturity ranges (min/max years) with unbounded and "all maturities" options.
"""

import csv
import io
from typing import List, Optional
from app.models.schemas import ParsedCollateralItem


def parse_collateral_csv(
    file_content: bytes,
    document_id: str
) -> List[ParsedCollateralItem]:
    """
    Parse CSV file containing collateral data.

    Expected CSV columns:
    - description (required)
    - market_value (required)
    - maturity_min (optional) - Minimum years to maturity
    - maturity_max (optional) - Maximum years to maturity
    - currency (optional, default USD)
    - valuation_scenario (optional, default to first scenario)

    Args:
        file_content: CSV file content as bytes
        document_id: CSA document ID for reference

    Returns:
        List of ParsedCollateralItem with validation errors if any
    """
    parsed_items = []

    try:
        # Decode bytes to string
        csv_text = file_content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_text))

        # Validate required columns
        required_columns = {'description', 'market_value'}
        optional_columns = {'maturity_min', 'maturity_max', 'currency', 'valuation_scenario'}

        if csv_reader.fieldnames is None:
            raise ValueError("CSV file is empty or has no headers")

        available_columns = set(csv_reader.fieldnames)
        missing_columns = required_columns - available_columns

        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

        # Parse each row
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (1 is headers)
            errors = []

            # Parse description
            description = row.get('description', '').strip()
            if not description:
                errors.append("Description is required")

            # Parse market_value
            market_value = 0.0
            market_value_str = row.get('market_value', '').strip()
            if not market_value_str:
                errors.append("Market value is required")
            else:
                try:
                    market_value = float(market_value_str.replace(',', ''))
                    if market_value <= 0:
                        errors.append("Market value must be positive")
                except ValueError:
                    errors.append(f"Invalid market value: '{market_value_str}'")

            # Parse maturity_min
            maturity_min = None
            maturity_min_str = row.get('maturity_min', '').strip()
            if maturity_min_str:
                try:
                    maturity_min = float(maturity_min_str)
                    if maturity_min < 0:
                        errors.append("Maturity min must be non-negative")
                except ValueError:
                    errors.append(f"Invalid maturity_min: '{maturity_min_str}'")

            # Parse maturity_max
            maturity_max = None
            maturity_max_str = row.get('maturity_max', '').strip()
            if maturity_max_str:
                try:
                    maturity_max = float(maturity_max_str)
                    if maturity_max < 0:
                        errors.append("Maturity max must be non-negative")
                except ValueError:
                    errors.append(f"Invalid maturity_max: '{maturity_max_str}'")

            # Validate maturity_min <= maturity_max
            if maturity_min is not None and maturity_max is not None:
                if maturity_min > maturity_max:
                    errors.append(f"Maturity min ({maturity_min}) cannot exceed max ({maturity_max})")

            # Parse currency
            currency = row.get('currency', '').strip().upper() or 'USD'

            # Parse valuation_scenario
            valuation_scenario = row.get('valuation_scenario', '').strip() or None

            # Create parsed item
            item = ParsedCollateralItem(
                csv_row_number=row_num,
                description=description,
                market_value=market_value,
                maturity_min=maturity_min,
                maturity_max=maturity_max,
                currency=currency,
                valuation_scenario=valuation_scenario,
                parse_errors=errors
            )

            parsed_items.append(item)

    except UnicodeDecodeError as e:
        # Return single error item for encoding issues
        return [
            ParsedCollateralItem(
                csv_row_number=0,
                description="",
                market_value=0.0,
                parse_errors=[f"File encoding error: {str(e)}. Please ensure the file is UTF-8 encoded."]
            )
        ]
    except ValueError as e:
        # Return single error item for structural issues
        return [
            ParsedCollateralItem(
                csv_row_number=0,
                description="",
                market_value=0.0,
                parse_errors=[f"CSV structure error: {str(e)}"]
            )
        ]
    except Exception as e:
        # Return single error item for unexpected issues
        return [
            ParsedCollateralItem(
                csv_row_number=0,
                description="",
                market_value=0.0,
                parse_errors=[f"Unexpected error parsing CSV: {str(e)}"]
            )
        ]

    return parsed_items


def validate_parsed_items(items: List[ParsedCollateralItem]) -> tuple[bool, List[str]]:
    """
    Validate all parsed items and return overall status.

    Returns:
        (is_valid, error_messages)
    """
    error_messages = []

    for item in items:
        if item.parse_errors:
            error_messages.append(
                f"Row {item.csv_row_number}: {', '.join(item.parse_errors)}"
            )

    is_valid = len(error_messages) == 0
    return is_valid, error_messages
