"""
Table Builder - Converts normalized collateral data into table format for display.

Takes normalized collateral items and pivots them into a table structure
with dynamic columns based on rating events.
"""

from typing import Dict, Any, List, Optional
from collections import defaultdict


class TableBuilder:
    """
    Builds table views from normalized collateral data.

    Handles both single-column and multi-column rating event structures.
    """

    @staticmethod
    def build_table_view(
        normalized_items: List[Dict[str, Any]],
        rating_events: List[str],
        is_multi_column: bool = True
    ) -> Dict[str, Any]:
        """
        Build a table view from normalized collateral items.

        Args:
            normalized_items: List of normalized collateral items
            rating_events: List of rating event names (column headers)
            is_multi_column: Whether multiple rating event columns exist

        Returns:
            Dict with 'columns' and 'rows' for table display
        """
        # Build column definitions
        columns = [
            {"key": "collateral_type", "label": "Collateral Type"},
            {"key": "maturity", "label": "Maturity"}
        ]

        # Add dynamic rating event columns
        for idx, event_name in enumerate(rating_events):
            columns.append({
                "key": f"rating_{idx}",
                "label": event_name
            })

        # Group items by (standardized_type, maturity_bucket)
        # This creates rows where each row represents a unique collateral + maturity combo
        row_groups = defaultdict(lambda: {
            "collateral_type": None,
            "collateral_type_display": None,
            "maturity": None,
            "maturity_min": None,
            "maturity_max": None,
            "rating_values": {}
        })

        for item in normalized_items:
            standardized_type = item.get("standardized_type", "UNKNOWN")
            maturity_buckets = item.get("maturity_buckets", [])
            rating_event_order = item.get("rating_event_order", 0)

            # Handle original collateral type for display
            collateral_type_display = item.get("collateral_type", standardized_type)

            # Process each maturity bucket
            if not maturity_buckets:
                # No maturity buckets - create a single row for this collateral
                row_key = (standardized_type, None, None)
                row_data = row_groups[row_key]
                row_data["collateral_type"] = standardized_type
                row_data["collateral_type_display"] = collateral_type_display
                row_data["maturity"] = "All"
                row_data["maturity_min"] = None
                row_data["maturity_max"] = None

                # Get valuation percentage (should be single value for "all")
                row_data["rating_values"][rating_event_order] = None
            else:
                # Process each maturity bucket
                for bucket in maturity_buckets:
                    min_years = bucket.get("min_maturity_years")
                    max_years = bucket.get("max_maturity_years")
                    valuation_pct = bucket.get("valuation_percentage")

                    row_key = (standardized_type, min_years, max_years)
                    row_data = row_groups[row_key]

                    row_data["collateral_type"] = standardized_type
                    row_data["collateral_type_display"] = collateral_type_display
                    row_data["maturity"] = TableBuilder._format_maturity(min_years, max_years)
                    row_data["maturity_min"] = min_years
                    row_data["maturity_max"] = max_years
                    row_data["rating_values"][rating_event_order] = valuation_pct

        # Convert row groups to list of rows
        rows = []
        for row_data in row_groups.values():
            row = {
                "collateral_type": row_data["collateral_type"],
                "collateral_type_display": row_data["collateral_type_display"],
                "maturity": row_data["maturity"],
                "maturity_min": row_data["maturity_min"],
                "maturity_max": row_data["maturity_max"]
            }

            # Add rating event values as columns
            for idx in range(len(rating_events)):
                row[f"rating_{idx}"] = row_data["rating_values"].get(idx)

            rows.append(row)

        # Sort rows by collateral type, then maturity
        rows.sort(key=lambda r: (
            r["collateral_type"],
            r["maturity_min"] if r["maturity_min"] is not None else -1,
            r["maturity_max"] if r["maturity_max"] is not None else 999
        ))

        return {
            "columns": columns,
            "rows": rows
        }

    @staticmethod
    def _format_maturity(min_years: Optional[float], max_years: Optional[float]) -> str:
        """
        Format maturity bucket into readable string.

        Args:
            min_years: Minimum maturity in years (None = no minimum)
            max_years: Maximum maturity in years (None = no maximum)

        Returns:
            Formatted string like "All Maturities", "0-1 years", "10+ years", etc.
        """
        if min_years is None and max_years is None:
            return "All Maturities"
        elif max_years is None:
            return f"{int(min_years)}+ years"
        elif min_years is None:
            year_word = "year" if max_years == 1 else "years"
            return f"Up to {int(max_years)} {year_word}"
        else:
            # Format as range
            return f"{int(min_years)}-{int(max_years)} years"

    @staticmethod
    def build_enhanced_response(
        agent_results: Dict[str, Any],
        rating_events: List[str],
        rating_event_count: int,
        is_multi_column: bool
    ) -> Dict[str, Any]:
        """
        Build enhanced API response with both flat items and table view.

        Args:
            agent_results: Results from collateral agent
            rating_events: List of rating event names
            rating_event_count: Number of rating event columns
            is_multi_column: Whether multiple columns exist

        Returns:
            Enhanced response with normalized_items, metadata, and table_view
        """
        # Extract normalized items from agent results
        collateral_data = agent_results.get("collateral", {})

        if hasattr(collateral_data, 'data'):
            collateral_data = collateral_data.data

        normalized_items = collateral_data.get("normalized_items", [])

        # Build metadata
        metadata = {
            "rating_events": rating_events,
            "rating_event_count": rating_event_count,
            "is_multi_column": is_multi_column,
            "total_items": len(normalized_items),
            "total_collateral_types": len(set(
                item.get("standardized_type") for item in normalized_items
            ))
        }

        # Build table view
        table_view = TableBuilder.build_table_view(
            normalized_items,
            rating_events,
            is_multi_column
        )

        return {
            "normalized_items": normalized_items,
            "metadata": metadata,
            "table_view": table_view
        }
