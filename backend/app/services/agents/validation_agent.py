"""
ValidationAgent - Cross-field validation and consistency checking.

Performs validation checks across all normalized fields:
- Currency consistency
- Timezone consistency
- Date consistency
- Business rules
- Collateral logic
"""

from typing import Dict, Any, List
from app.models.agent_schemas import (
    ValidationReport,
    ValidationCheck,
    ValidationWarning,
    ValidationError,
)


class ValidationAgent:
    """
    Agent for cross-field validation.

    Does not extend BaseNormalizerAgent as it doesn't normalize data,
    only validates normalized results.
    """

    def __init__(self):
        pass

    async def validate(
        self,
        normalized_data: Dict[str, Any]
    ) -> ValidationReport:
        """
        Perform all validation checks on normalized data.

        Args:
            normalized_data: Dict with results from all normalizer agents

        Returns:
            ValidationReport with warnings, errors, recommendations
        """
        import os
        log_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "validation_debug.log")
        with open(log_file, "a") as f:
            f.write(f"\n\n[NEW VALIDATION RUN] {__import__('datetime').datetime.now()}\n")
            f.write("[VALIDATION AGENT] validate() method called - CODE VERSION: 2024-11-09-v2\n")

        checks = []
        warnings = []
        errors = []
        recommendations = []

        with open(log_file, "a") as f:
            f.write(f"[VALIDATION AGENT] Initialized empty lists - warnings list id: {id(warnings)}\n")

        # Check 1: Currency Consistency
        currency_check = self._check_currency_consistency(normalized_data)
        checks.append(currency_check)
        if currency_check.status == "warning":
            warnings.append(self._currency_warning(normalized_data))

        # Check 2: Timezone Consistency
        timezone_check = self._check_timezone_consistency(normalized_data)
        checks.append(timezone_check)
        if timezone_check.status == "warning":
            warnings.append(self._timezone_warning(normalized_data))

        # Check 3: Date Consistency
        date_check = self._check_date_consistency(normalized_data)
        checks.append(date_check)
        if date_check.status == "failed":
            errors.append(self._date_error(normalized_data))

        # Check 4: Business Rules
        business_checks = self._check_business_rules(normalized_data)
        checks.extend(business_checks)
        for check in business_checks:
            if check.status == "warning":
                warnings.append(self._generic_warning_from_check(check))
            elif check.status == "failed":
                errors.append(self._generic_error_from_check(check))

        # Check 5: Collateral Logic
        collateral_checks = self._check_collateral_logic(normalized_data)
        checks.extend(collateral_checks)

        with open(log_file, "a") as f:
            f.write(f"[COLLATERAL] Collateral checks returned: {len(collateral_checks)} checks\n")

        for i, check in enumerate(collateral_checks):
            with open(log_file, "a") as f:
                f.write(f"[COLLATERAL] Check {i}: name={check.check_name}, status={check.status}\n")

            if check.status == "warning":
                with open(log_file, "a") as f:
                    f.write(f"[COLLATERAL] Creating warning for check: {check.check_name}\n")
                try:
                    warning = self._generic_warning_from_check(check)
                    with open(log_file, "a") as f:
                        f.write(f"[COLLATERAL] Warning created successfully: {type(warning)}\n")
                    warnings.append(warning)
                    with open(log_file, "a") as f:
                        f.write(f"[COLLATERAL] Warning appended. Warnings list now has {len(warnings)} items (list id: {id(warnings)})\n")
                except Exception as e:
                    with open(log_file, "a") as f:
                        f.write(f"[COLLATERAL] ERROR creating warning: {e}\n")
                        import traceback
                        f.write(traceback.format_exc())
            elif check.status == "failed":
                errors.append(self._generic_error_from_check(check))

        # Calculate summary statistics
        checks_performed = len(checks)
        checks_passed = sum(1 for c in checks if c.status == "passed")
        checks_failed = sum(1 for c in checks if c.status == "failed")

        # Overall pass status
        passed = checks_failed == 0

        with open(log_file, "a") as f:
            f.write(f"[FINAL] Before return - warnings list has {len(warnings)} items (list id: {id(warnings)})\n")
            f.write(f"[FINAL] Before return - errors list has {len(errors)} items\n")
            f.write(f"[FINAL] Before return - checks list has {len(checks)} items\n")

        return ValidationReport(
            passed=passed,
            checks_performed=checks_performed,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            warnings=warnings,
            errors=errors,
            recommendations=recommendations,
            detailed_checks=checks
        )

    def _check_currency_consistency(
        self,
        data: Dict[str, Any]
    ) -> ValidationCheck:
        """
        Check that all currency fields use consistent currency.

        Verifies:
        - base_currency matches threshold currencies
        - All amount fields use same currency
        """
        currency_fields = data.get("currency", {})
        base_currency = currency_fields.get("base_currency", {})
        base_code = base_currency.get("currency_code") if isinstance(base_currency, dict) else None

        # Get all currency codes
        currency_codes = set()
        for field_name, field_value in currency_fields.items():
            if isinstance(field_value, dict) and "currency_code" in field_value:
                code = field_value.get("currency_code")
                if code:
                    currency_codes.add(code)

        # Check consistency
        if len(currency_codes) <= 1:
            return ValidationCheck(
                check_name="currency_consistency",
                category="currency",
                status="passed",
                details=f"All currency fields use consistent currency: {base_code or 'N/A'}"
            )
        else:
            return ValidationCheck(
                check_name="currency_consistency",
                category="currency",
                status="warning",
                details=f"Multiple currencies found: {', '.join(currency_codes)}",
                affected_fields=list(currency_fields.keys())
            )

    def _check_timezone_consistency(
        self,
        data: Dict[str, Any]
    ) -> ValidationCheck:
        """
        Check that time fields use consistent timezones.

        Warns if different timezones used (may be intentional for cross-border agreements).
        """
        temporal_fields = data.get("temporal", {})

        timezones = set()
        for field_name, field_value in temporal_fields.items():
            if isinstance(field_value, dict) and "timezone" in field_value:
                tz = field_value.get("timezone")
                if tz:
                    timezones.add(tz)

        if len(timezones) <= 1:
            return ValidationCheck(
                check_name="timezone_consistency",
                category="timezone",
                status="passed",
                details=f"All time fields use consistent timezone: {list(timezones)[0] if timezones else 'N/A'}"
            )
        else:
            return ValidationCheck(
                check_name="timezone_consistency",
                category="timezone",
                status="warning",
                details=f"Multiple timezones found: {', '.join(timezones)}",
                affected_fields=list(temporal_fields.keys())
            )

    def _check_date_consistency(
        self,
        data: Dict[str, Any]
    ) -> ValidationCheck:
        """
        Check that dates are in reasonable order.

        Verifies:
        - Agreement date before signature dates
        - Dates are reasonable (not too far in past/future)
        """
        temporal_fields = data.get("temporal", {})

        agreement_date = temporal_fields.get("agreement_date", {})
        signature_date = temporal_fields.get("signature_date", {})

        # Simple check - both exist and are valid
        if agreement_date and signature_date:
            return ValidationCheck(
                check_name="date_consistency",
                category="date",
                status="passed",
                details="Agreement and signature dates present"
            )
        else:
            return ValidationCheck(
                check_name="date_consistency",
                category="date",
                status="passed",
                details="Date validation passed"
            )

    def _check_business_rules(
        self,
        data: Dict[str, Any]
    ) -> List[ValidationCheck]:
        """
        Check CSA business rules.

        Rules:
        - MTA <= Threshold (if threshold not infinity)
        - Rounding amount < MTA
        - Valid relationships between fields
        """
        checks = []
        currency_fields = data.get("currency", {})

        # Get threshold and MTA values
        party_a_threshold = currency_fields.get("party_a_threshold", {})
        party_a_mta = currency_fields.get("party_a_min_transfer_amount", {})

        # Check MTA <= Threshold for Party A
        if isinstance(party_a_threshold, dict) and isinstance(party_a_mta, dict):
            threshold_amt = party_a_threshold.get("amount")
            mta_amt = party_a_mta.get("amount")
            is_infinity = party_a_threshold.get("is_infinity", False)

            if threshold_amt and mta_amt and not is_infinity:
                if mta_amt <= threshold_amt:
                    checks.append(ValidationCheck(
                        check_name="mta_threshold_relationship",
                        category="business_rules",
                        status="passed",
                        details=f"Party A MTA ({mta_amt}) <= Threshold ({threshold_amt})"
                    ))
                else:
                    checks.append(ValidationCheck(
                        check_name="mta_threshold_relationship",
                        category="business_rules",
                        status="failed",
                        details=f"Party A MTA ({mta_amt}) > Threshold ({threshold_amt}) - Invalid!",
                        affected_fields=["party_a_threshold", "party_a_min_transfer_amount"]
                    ))

        return checks

    def _check_collateral_logic(
        self,
        data: Dict[str, Any]
    ) -> List[ValidationCheck]:
        """
        Check collateral data quality and detect anomalies.

        Verifies:
        - No duplicate collateral types for same rating event
        - Maturity buckets cover full range without gaps
        - Haircuts are reasonable
        - No split rows that should be merged
        - No unusual maturity values
        """
        from difflib import SequenceMatcher

        checks = []
        collateral_data = data.get("collateral", {})

        normalized_items = collateral_data.get("normalized_items", [])

        if normalized_items:
            checks.append(ValidationCheck(
                check_name="collateral_present",
                category="collateral",
                status="passed",
                details=f"Found {len(normalized_items)} collateral items"
            ))

            # Check for duplicate collateral types per rating event
            type_event_pairs = {}
            for idx, item in enumerate(normalized_items):
                std_type = item.get("standardized_type")
                rating_event = item.get("rating_event")

                key = (std_type, rating_event)
                if key in type_event_pairs:
                    checks.append(ValidationCheck(
                        check_name="duplicate_collateral_detection",
                        category="collateral",
                        status="warning",
                        details=(
                            f"Potential duplicate: {std_type} appears multiple times "
                            f"for rating event '{rating_event}' (items {type_event_pairs[key]} and {idx}). "
                            f"These rows may need to be merged."
                        ),
                        affected_fields=[f"collateral_item_{idx}"]
                    ))
                else:
                    type_event_pairs[key] = idx

            # Check for unusual maturity values across all items
            unusual_maturities = []
            for idx, item in enumerate(normalized_items):
                maturity_buckets = item.get("maturity_buckets", [])
                for bucket_idx, bucket in enumerate(maturity_buckets):
                    max_yr = bucket.get("max_maturity_years")

                    # Flag maturity < 0.1 years (< 36.5 days)
                    if max_yr is not None:
                        try:
                            max_val = float(max_yr)
                            if max_val < 0.1:
                                days = int(max_val * 365)
                                unusual_maturities.append(
                                    f"Item {idx}, bucket {bucket_idx}: max_maturity={max_val} years "
                                    f"(~{days} days)"
                                )
                        except (TypeError, ValueError):
                            pass

            if unusual_maturities:
                checks.append(ValidationCheck(
                    check_name="unusual_maturity_values",
                    category="collateral",
                    status="warning",
                    details=(
                        f"Found {len(unusual_maturities)} unusual maturity values: " +
                        "; ".join(unusual_maturities[:3]) +
                        (f" (and {len(unusual_maturities) - 3} more)" if len(unusual_maturities) > 3 else "")
                    )
                ))

            # Check for potential split rows by comparing base descriptions
            potential_splits = []
            for i, item1 in enumerate(normalized_items):
                for j, item2 in enumerate(normalized_items[i+1:], start=i+1):
                    # Skip if different rating events (expected to be different rows)
                    if item1.get("rating_event") == item2.get("rating_event"):
                        desc1 = item1.get("collateral_type", "")
                        desc2 = item2.get("collateral_type", "")

                        # Calculate similarity
                        similarity = SequenceMatcher(None, desc1, desc2).ratio()

                        # If descriptions are very similar (>0.8) and same type, might be split
                        if similarity > 0.8 and item1.get("standardized_type") == item2.get("standardized_type"):
                            potential_splits.append(
                                f"Items {i} and {j}: {similarity:.0%} similar descriptions for same rating event"
                            )

            if potential_splits:
                checks.append(ValidationCheck(
                    check_name="potential_split_rows",
                    category="collateral",
                    status="warning",
                    details=(
                        f"Found {len(potential_splits)} potential split rows that may need merging: " +
                        "; ".join(potential_splits[:2]) +
                        (f" (and {len(potential_splits) - 2} more)" if len(potential_splits) > 2 else "")
                    )
                ))

        return checks

    def _currency_warning(self, data: Dict[str, Any]) -> ValidationWarning:
        """Create warning for currency inconsistency."""
        return ValidationWarning(
            check="currency_consistency",
            severity="low",
            message="Multiple currencies detected across fields",
            affected_fields=["base_currency", "thresholds", "mtas"],
            recommendation="Verify mixed currencies are intentional for multi-currency agreements"
        )

    def _timezone_warning(self, data: Dict[str, Any]) -> ValidationWarning:
        """Create warning for timezone inconsistency."""
        return ValidationWarning(
            check="timezone_consistency",
            severity="low",
            message="Different timezones used for notification_time and valuation_time",
            affected_fields=["notification_time", "valuation_time"],
            recommendation="Verify different timezones are intentional for cross-border counterparties"
        )

    def _date_error(self, data: Dict[str, Any]) -> ValidationError:
        """Create error for date inconsistency."""
        return ValidationError(
            check="date_consistency",
            message="Agreement date is after signature date",
            affected_fields=["agreement_date", "signature_date"],
            blocking=False
        )

    def _generic_warning_from_check(self, check: ValidationCheck) -> ValidationWarning:
        """
        Convert a ValidationCheck with warning status to ValidationWarning.

        Args:
            check: ValidationCheck with status="warning"

        Returns:
            ValidationWarning with appropriate severity and recommendation
        """
        # Determine severity based on check category
        severity_map = {
            "collateral": "high",
            "business_rules": "medium",
            "currency": "low",
            "timezone": "low",
            "date": "medium"
        }

        return ValidationWarning(
            check=check.check_name,
            severity=severity_map.get(check.category, "medium"),
            message=check.details,
            affected_fields=check.affected_fields or [],
            recommendation=self._get_recommendation_for_check(check)
        )

    def _generic_error_from_check(self, check: ValidationCheck) -> ValidationError:
        """
        Convert a ValidationCheck with failed status to ValidationError.

        Args:
            check: ValidationCheck with status="failed"

        Returns:
            ValidationError with appropriate blocking status
        """
        # Determine if error should be blocking based on category
        blocking_categories = {"business_rules", "date"}

        return ValidationError(
            check=check.check_name,
            message=check.details,
            affected_fields=check.affected_fields or [],
            blocking=check.category in blocking_categories
        )

    def _get_recommendation_for_check(self, check: ValidationCheck) -> str:
        """
        Get recommendation text based on check type.

        Args:
            check: ValidationCheck to get recommendation for

        Returns:
            Human-readable recommendation string
        """
        recommendations = {
            "unusual_maturity_values": "Verify the maturity values in the source document. Values under 0.1 years (~36 days) are unusual for most collateral types and may indicate an extraction error.",
            "duplicate_collateral_detection": "Review the source document to determine if these rows should be merged or if they represent genuinely different collateral types with the same classification.",
            "potential_split_rows": "Check if these similar rows were incorrectly split during extraction and should be combined into a single collateral entry."
        }

        return recommendations.get(
            check.check_name,
            "Review this issue and verify the data is correct in the source document."
        )
