from __future__ import annotations

from decimal import Decimal, InvalidOperation

from agents.recovery.adapters import parse_csv_rows
from agents.recovery.domain.validation import RecoveryInputError


def adapt_fee_report(raw: bytes | str) -> list[dict[str, object]]:
    charges: list[dict[str, object]] = []
    for row in parse_csv_rows(raw):
        report_type = row.get("report_type")
        if report_type != "fee_report":
            if report_type in {"reimbursement_report", "inventory_adjustment"}:
                charges.append(
                    {
                        "manager": "fee_report",
                        "line_id": row.get("line_id"),
                        "org_id": row.get("org_id"),
                        "unit_id": row.get("unit_id"),
                        "report_type": report_type,
                        "amount_usd": row.get("amount_usd"),
                        "posted_date": row.get("posted_date"),
                        "line_kind": "unresolved_ledger_candidate",
                        "verdict": "uncertain",
                    }
                )
                continue
            raise RecoveryInputError("fee report has an unsupported report_type")
        try:
            amount = Decimal(row["amount_usd"])
            charged_at = row["posted_date"]
            quantity = int(row["quantity"])
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise RecoveryInputError("fee report contains invalid amount, date, or quantity") from exc
        if (
            not amount.is_finite()
            or amount < 0
            or amount.as_tuple().exponent < -2
            or amount != amount.quantize(Decimal("0.01"))
        ):
            raise RecoveryInputError("fee amount must be non-negative exact cents")
        if quantity <= 0:
            raise RecoveryInputError("fee quantity must be positive")
        shipment_id = row.get("fba_shipment_id") or None
        order_id = row.get("order_id") or None
        granularity = "unit" if row.get("unit_id") else "order" if order_id else "shipment" if shipment_id else "unit"
        charge_type = row["charge_type"]
        normalized_type, normalized_subtype = (
            ("warehouse_lost", "lost") if charge_type == "lost_inbound" else (charge_type, charge_type)
        )
        charges.append(
            {
                "manager": "fee_report",
                "charge_id": row["line_id"],
                "charge_type": normalized_type,
                "charge_subtype": normalized_subtype,
                "charged_at": charged_at,
                "granularity": granularity,
                "shipment_id": shipment_id,
                "amazon_order_id": order_id,
                "sku": row["sku"],
                "fnsku": row.get("fnsku") or None,
                "asin": None,
                "quantity": quantity,
                "currency": "USD",
                "amount_per_unit": None,
                "amount_total": str(amount),
                "description": row["charge_type"],
                "org_id": row["org_id"],
                "unit_id": row.get("unit_id"),
                "synthetic_source_data": True,
                "line_kind": "charge_candidate",
            }
        )
    return charges