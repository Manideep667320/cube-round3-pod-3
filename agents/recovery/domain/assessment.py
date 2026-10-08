from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from agents.recovery.domain.canonical import Charge, ContractEvidence, RecoveryRule, Reimbursement
from agents.recovery.domain.ledger import InternalDecisionFacts, net_reimbursement

ContractVerdict = Literal[
    "contested", "accepted", "insufficient_evidence", "already_reimbursed", "out_of_window"
]
Position = Literal["SUPPORTS", "CONTRADICTS", "SILENT"]
_MAPPINGS: dict[tuple[str, str], frozenset[str]] = {
    ("inbound_defect", "unbagged_unit"): frozenset({"polybag_present"}),
    ("inbound_defect", "missing_suffocation_warning"): frozenset(
        {"suffocation_warning_present", "suffocation_warning_legible"}
    ),
    ("inbound_defect", "unscannable_barcode"): frozenset(
        {"fnsku_label_flat", "fnsku_label_placement_valid"}
    ),
    ("inbound_defect", "manufacturer_barcode_visible"): frozenset({"manufacturer_barcode_covered"}),
    ("unplanned_prep", "labelling"): frozenset({"fnsku_label_placement_valid"}),
    ("unplanned_prep", "bagging"): frozenset({"polybag_present", "polybag_sealed"}),
    ("warehouse_lost", "lost"): frozenset({"quantity_matches_po"}),
    ("mis_ship", "mis_ship"): frozenset({"all_items_present", "quantities_correct"}),
}


@dataclass(frozen=True)
class ContractDecision:
    verdict: ContractVerdict
    reason: str
    remaining_amount: Decimal | None
    currency: str | None
    position: Position


def required_checks(charge: Charge) -> frozenset[str] | None:
    charge_type = charge.charge_type.strip().lower().replace("-", "_").replace(" ", "_")
    subtype = charge.charge_subtype.strip().lower().replace("-", "_").replace(" ", "_")
    direct = _MAPPINGS.get((charge_type, subtype))
    if direct is not None:
        return direct
    if charge_type == "warehouse_lost":
        return _MAPPINGS[("warehouse_lost", "lost")]
    if charge_type == "mis_ship":
        return _MAPPINGS[("mis_ship", "mis_ship")]
    return None


def relevant(charge: Charge, record: ContractEvidence) -> bool:
    if record.observed_at > charge.charged_at:
        return False
    if charge.granularity == "shipment":
        return record.granularity == "shipment" and charge.shipment_id is not None and record.shipment_id == charge.shipment_id
    if charge.granularity == "order":
        return record.granularity == "order" and charge.amazon_order_id is not None and record.amazon_order_id == charge.amazon_order_id
    return record.granularity == "unit" and record.attributed_charge_id == charge.charge_id


def position_for_charge(charge: Charge, evidence: tuple[ContractEvidence, ...]) -> Position:
    required = required_checks(charge)
    if required is None:
        return "SILENT"
    relevant_records = tuple(item for item in evidence if relevant(charge, item) and item.check_key in required)
    if any(item.verdict == "fail" for item in relevant_records):
        return "SUPPORTS"
    if {item.check_key for item in relevant_records if item.verdict == "pass"} == required:
        return "CONTRADICTS"
    return "SILENT"


def project_contract_verdict(
    charge: Charge,
    credits: tuple[Reimbursement, ...],
    evidence: tuple[ContractEvidence, ...],
    rule: RecoveryRule,
    facts: InternalDecisionFacts,
    evaluated_on: date,
) -> ContractDecision:
    """Adapted from recovery_contract.py; does not invent eligibility policy."""
    position = position_for_charge(charge, evidence)
    reimbursed = net_reimbursement(charge, credits)
    if reimbursed >= charge.amount_total:
        return ContractDecision("already_reimbursed", "NET_REIMBURSEMENT_COVERS_CHARGE", Decimal("0"), charge.currency, position)
    if not facts.economic_state_known or not facts.current:
        return ContractDecision("insufficient_evidence", "INTERNAL_STATE_NOT_ACTIONABLE", None, None, position)
    required = required_checks(charge)
    if required is None:
        return ContractDecision("insufficient_evidence", "NO_AUTHORITATIVE_CHARGE_MAPPING", None, None, position)
    scoped = tuple(item for item in evidence if relevant(charge, item) and item.check_key in required)
    if any(item.verdict == "fail" for item in scoped):
        return ContractDecision("accepted", "RELEVANT_CHECK_FAILED", None, None, position)
    if {item.check_key for item in scoped if item.verdict == "pass"} != required:
        return ContractDecision("insufficient_evidence", "EVIDENCE_INCOMPLETE_OR_UNCERTAIN", None, None, position)
    if not rule.authority_available or rule.claim_window_days is None:
        return ContractDecision("insufficient_evidence", "RULE_WINDOW_UNAVAILABLE", None, None, position)
    if (evaluated_on - charge.charged_at).days > rule.claim_window_days:
        return ContractDecision("out_of_window", "FILING_WINDOW_CLOSED", None, None, position)
    remaining = min(charge.amount_total - reimbursed, facts.remaining_actionable)
    if remaining <= 0:
        return ContractDecision("already_reimbursed", "NO_ACTIONABLE_RESIDUAL", Decimal("0"), charge.currency, position)
    return ContractDecision("contested", "SUPPORTED_CURRENT_RESIDUAL", remaining, charge.currency, position)