from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal, cast

from agents.recovery.domain.validation import (
    CHECK_KEY_REGISTRY,
    RecoveryInputError,
    currency_value,
    date_value,
    money_value,
    text_value,
    validate_fields,
)

Granularity = Literal["unit", "shipment", "order"]
EvidenceVerdict = Literal["pass", "fail", "uncertain"]

_CHARGE_FIELDS = frozenset(
    {
        "charge_id", "charge_type", "charge_subtype", "charged_at", "granularity", "shipment_id",
        "amazon_order_id", "sku", "fnsku", "asin", "quantity", "currency", "amount_per_unit",
        "amount_total", "description",
    }
)
_CREDIT_FIELDS = frozenset(
    {
        "reimbursement_id", "case_id", "approval_date", "amazon_order_id", "sku", "fnsku", "asin",
        "reason", "condition", "currency", "amount_per_unit", "amount_total",
        "quantity_reimbursed_cash", "quantity_reimbursed_inventory", "original_reimbursement_id",
    }
)


@dataclass(frozen=True)
class Charge:
    charge_id: str
    charge_type: str
    charge_subtype: str
    charged_at: date
    granularity: Granularity
    shipment_id: str | None
    amazon_order_id: str | None
    sku: str
    fnsku: str | None
    asin: str | None
    quantity: int
    currency: str
    amount_per_unit: Decimal | None
    amount_total: Decimal
    description: str

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> Charge:
        validate_fields(raw, _CHARGE_FIELDS, "charge")
        granularity = raw.get("granularity")
        if granularity not in {"unit", "shipment", "order"}:
            raise RecoveryInputError("charge granularity is invalid")
        quantity = raw.get("quantity")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise RecoveryInputError("charge quantity must be a positive integer")
        per_unit = raw.get("amount_per_unit")
        return cls(
            charge_id=cast(str, text_value(raw.get("charge_id"), "charge_id")),
            charge_type=cast(str, text_value(raw.get("charge_type"), "charge_type")),
            charge_subtype=cast(str, text_value(raw.get("charge_subtype"), "charge_subtype")),
            charged_at=date_value(raw.get("charged_at"), "charged_at"),
            granularity=cast(Granularity, granularity),
            shipment_id=text_value(raw.get("shipment_id"), "shipment_id", nullable=True),
            amazon_order_id=text_value(raw.get("amazon_order_id"), "amazon_order_id", nullable=True),
            sku=cast(str, text_value(raw.get("sku"), "sku")),
            fnsku=text_value(raw.get("fnsku"), "fnsku", nullable=True),
            asin=text_value(raw.get("asin"), "asin", nullable=True),
            quantity=quantity,
            currency=currency_value(raw.get("currency")),
            amount_per_unit=None if per_unit is None else money_value(per_unit, "amount_per_unit"),
            amount_total=money_value(raw.get("amount_total"), "amount_total"),
            description=cast(str, text_value(raw.get("description"), "description")),
        )


@dataclass(frozen=True)
class Reimbursement:
    reimbursement_id: str
    case_id: str | None
    approval_date: date
    amazon_order_id: str | None
    sku: str
    fnsku: str | None
    asin: str | None
    reason: str
    condition: str | None
    currency: str
    amount_per_unit: Decimal
    amount_total: Decimal
    quantity_reimbursed_cash: int
    quantity_reimbursed_inventory: int
    original_reimbursement_id: str | None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> Reimbursement:
        validate_fields(raw, _CREDIT_FIELDS, "reimbursement")
        names = ("quantity_reimbursed_cash", "quantity_reimbursed_inventory")
        if any(not isinstance(raw.get(name), int) or isinstance(raw.get(name), bool) or raw[name] < 0 for name in names):
            raise RecoveryInputError("reimbursement quantities must be non-negative integers")
        return cls(
            reimbursement_id=cast(str, text_value(raw.get("reimbursement_id"), "reimbursement_id")),
            case_id=text_value(raw.get("case_id"), "case_id", nullable=True),
            approval_date=date_value(raw.get("approval_date"), "approval_date"),
            amazon_order_id=text_value(raw.get("amazon_order_id"), "amazon_order_id", nullable=True),
            sku=cast(str, text_value(raw.get("sku"), "sku")),
            fnsku=text_value(raw.get("fnsku"), "fnsku", nullable=True),
            asin=text_value(raw.get("asin"), "asin", nullable=True),
            reason=cast(str, text_value(raw.get("reason"), "reason")),
            condition=text_value(raw.get("condition"), "condition", nullable=True),
            currency=currency_value(raw.get("currency")),
            amount_per_unit=money_value(raw.get("amount_per_unit"), "amount_per_unit"),
            amount_total=money_value(raw.get("amount_total"), "amount_total", signed=True),
            quantity_reimbursed_cash=raw["quantity_reimbursed_cash"],
            quantity_reimbursed_inventory=raw["quantity_reimbursed_inventory"],
            original_reimbursement_id=text_value(
                raw.get("original_reimbursement_id"), "original_reimbursement_id", nullable=True
            ),
        )


@dataclass(frozen=True)
class ContractEvidence:
    manager: str
    check_key: str
    verdict: EvidenceVerdict
    observed_at: date
    granularity: Granularity
    shipment_id: str | None = None
    amazon_order_id: str | None = None
    attributed_charge_id: str | None = None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> ContractEvidence:
        manager = raw.get("manager")
        check_key = raw.get("check_key")
        verdict = raw.get("verdict")
        granularity = raw.get("granularity")
        if manager not in CHECK_KEY_REGISTRY or check_key not in CHECK_KEY_REGISTRY[manager]:
            raise RecoveryInputError("evidence check_key is not in the supplied registry")
        if verdict not in {"pass", "fail", "uncertain"}:
            raise RecoveryInputError("evidence verdict is invalid")
        if granularity not in {"unit", "shipment", "order"}:
            raise RecoveryInputError("evidence granularity is invalid")
        return cls(
            manager=manager,
            check_key=check_key,
            verdict=cast(EvidenceVerdict, verdict),
            observed_at=date_value(raw.get("observed_at"), "observed_at"),
            granularity=cast(Granularity, granularity),
            shipment_id=text_value(raw.get("shipment_id"), "shipment_id", nullable=True),
            amazon_order_id=text_value(raw.get("amazon_order_id"), "amazon_order_id", nullable=True),
            attributed_charge_id=text_value(
                raw.get("attributed_charge_id"), "attributed_charge_id", nullable=True
            ),
        )


@dataclass(frozen=True)
class RecoveryRule:
    authority_available: bool
    claim_window_days: int | None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> RecoveryRule:
        available = raw.get("authority_available")
        window = raw.get("claim_window_days")
        if not isinstance(available, bool):
            raise RecoveryInputError("authority_available must be boolean")
        if window is not None and (not isinstance(window, int) or isinstance(window, bool) or window < 0):
            raise RecoveryInputError("claim window must be a non-negative integer or null")
        return cls(available, window)