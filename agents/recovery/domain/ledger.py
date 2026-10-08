from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from agents.recovery.domain.canonical import Charge, Reimbursement
from agents.recovery.domain.validation import RecoveryInputError


@dataclass(frozen=True)
class InternalDecisionFacts:
    """Trusted facts exported by the economic recovery engine."""

    economic_state_known: bool
    current: bool
    remaining_actionable: Decimal
    active_pursuit: Decimal


def same_subject(charge: Charge, credit: Reimbursement) -> bool:
    pairs = (
        (charge.amazon_order_id, credit.amazon_order_id),
        (charge.sku, credit.sku),
        (charge.fnsku, credit.fnsku),
        (charge.asin, credit.asin),
    )
    shared = [(left, right) for left, right in pairs if left is not None and right is not None]
    return bool(shared) and all(left == right for left, right in shared)


def net_reimbursement(charge: Charge, credits: tuple[Reimbursement, ...]) -> Decimal:
    """Compute currency-exact credits and explicit negative adjustment lineage."""
    matching = [item for item in credits if item.currency == charge.currency and same_subject(charge, item)]
    roots = {item.reimbursement_id: item for item in matching if item.original_reimbursement_id is None}
    total = Decimal("0")
    for item in matching:
        if item.original_reimbursement_id is None:
            total += item.amount_total
        elif item.original_reimbursement_id not in roots or item.amount_total >= 0:
            raise RecoveryInputError("reimbursement adjustment lineage is ambiguous")
        else:
            total += item.amount_total
    return max(total, Decimal("0"))