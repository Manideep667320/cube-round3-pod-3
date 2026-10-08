from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


class RecoveryInputError(ValueError):
    """A recovery input is malformed or too ambiguous to evaluate safely."""


CHECK_KEY_REGISTRY: dict[str, frozenset[str]] = {
    "receiving": frozenset(
        {"identity_matches_po", "quantity_matches_po", "carton_undamaged", "unit_undamaged", "variant_correct"}
    ),
    "prep": frozenset(
        {
            "polybag_present", "polybag_sealed", "suffocation_warning_present",
            "suffocation_warning_legible", "fnsku_label_flat", "fnsku_label_placement_valid",
            "manufacturer_barcode_covered", "expiry_date_legible", "handling_marks_present",
        }
    ),
    "pack": frozenset({"all_items_present", "quantities_correct", "no_extra_items", "order_matches_manifest"}),
    "returns": frozenset(
        {"identity_matches_order", "completeness_verified", "condition_grade", "disposition_assigned"}
    ),
}

OPTIONAL_FIELDS = frozenset(
    {
        "case_id", "condition", "original_reimbursement_id", "shipment_id", "amazon_order_id",
        "fnsku", "asin", "amount_per_unit", "attributed_charge_id",
    }
)


def validate_fields(raw: dict[str, Any], fields: frozenset[str], name: str) -> None:
    unknown = set(raw) - fields
    missing = {field for field in fields - OPTIONAL_FIELDS if field not in raw}
    if unknown or missing:
        raise RecoveryInputError(
            f"{name} fields invalid: unknown={sorted(unknown)}, missing={sorted(missing)}"
        )


def text_value(value: object, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RecoveryInputError(f"{field} must be a non-empty string")
    return value


def currency_value(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Z]{3}", value, flags=re.ASCII) is None:
        raise RecoveryInputError("currency must match [A-Z]{3}")
    return value


def money_value(value: object, field: str, *, signed: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, str | int | Decimal):
        raise RecoveryInputError(f"{field} must be a decimal string or integer")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise RecoveryInputError(f"{field} is not decimal") from exc
    if not result.is_finite() or (not signed and result < 0):
        raise RecoveryInputError(f"{field} must be a finite {'signed' if signed else 'non-negative'} decimal")
    return result


def date_value(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise RecoveryInputError(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RecoveryInputError(f"{field} must be an ISO date") from exc