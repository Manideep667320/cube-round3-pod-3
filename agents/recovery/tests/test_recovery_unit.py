from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from agents.recovery.domain.assessment import project_contract_verdict
from agents.recovery.domain.canonical import Charge, ContractEvidence, RecoveryRule, Reimbursement
from agents.recovery.domain.ledger import InternalDecisionFacts, net_reimbursement
from agents.recovery.domain.validation import RecoveryInputError
from agents.recovery.fail_open import fail_open_boundary
from agents.recovery.tenancy import assert_same_org, tenant_scope


def charge() -> Charge:
    return Charge(
        charge_id="charge-1", charge_type="inbound_defect", charge_subtype="unbagged_unit",
        charged_at=date(2026, 6, 1), granularity="unit", shipment_id="ship-1",
        amazon_order_id="order-1", sku="sku-1", fnsku="fnsku-1", asin=None,
        quantity=1, currency="USD", amount_per_unit=None, amount_total=Decimal("4.25"),
        description="synthetic test charge",
    )


def test_complete_evidence_and_current_authority_projects_residual() -> None:
    evidence = (ContractEvidence("prep", "polybag_present", "pass", date(2026, 5, 1), "unit", attributed_charge_id="charge-1"),)
    decision = project_contract_verdict(
        charge(), (), evidence, RecoveryRule(True, 60),
        InternalDecisionFacts(True, True, Decimal("3.00"), Decimal("0")), date(2026, 6, 1),
    )
    assert decision.verdict == "contested"
    assert decision.remaining_amount == Decimal("3.00")
    assert decision.position == "CONTRADICTS"


def test_unknown_rule_or_evidence_stays_uncertain() -> None:
    decision = project_contract_verdict(
        charge(), (), (), RecoveryRule(False, None),
        InternalDecisionFacts(True, True, Decimal("4.25"), Decimal("0")), date(2026, 6, 1),
    )
    assert decision.verdict == "insufficient_evidence"
    assert decision.remaining_amount is None


def test_tenant_context_refuses_cross_org_access() -> None:
    with tenant_scope("org-a", {"org-a"}):
        with pytest.raises(LookupError):
            assert_same_org("org-b")


def test_fail_open_returns_pending_uncertain() -> None:
    @fail_open_boundary
    def fail() -> None:
        raise RuntimeError("private detail")

    result = fail()
    assert result == {
        "verdict": "uncertain", "status": "pending",
        "reason": "DECISION_UNAVAILABLE", "error_type": "RuntimeError",
    }


def test_invalid_currency_is_rejected() -> None:
    with pytest.raises(RecoveryInputError):
        Charge.from_mapping({"currency": "usd"})


def test_reimbursement_reversal_is_currency_and_lineage_exact() -> None:
    root = Reimbursement(
        "credit-1", None, date(2026, 6, 2), "order-1", "sku-1", "fnsku-1", None,
        "reimbursement", None, "USD", Decimal("1.25"), Decimal("1.25"), 1, 0, None,
    )
    reversal = Reimbursement(
        "credit-2", None, date(2026, 6, 3), "order-1", "sku-1", "fnsku-1", None,
        "reversal", None, "USD", Decimal("0.25"), Decimal("-0.25"), 0, 0, "credit-1",
    )
    assert net_reimbursement(charge(), (root, reversal)) == Decimal("1.00")


def test_reimbursement_adjustment_without_root_fails_closed() -> None:
    adjustment = Reimbursement(
        "credit-2", None, date(2026, 6, 3), "order-1", "sku-1", "fnsku-1", None,
        "reversal", None, "USD", Decimal("0.25"), Decimal("-0.25"), 0, 0, "missing-root",
    )
    with pytest.raises(RecoveryInputError):
        net_reimbursement(charge(), (adjustment,))