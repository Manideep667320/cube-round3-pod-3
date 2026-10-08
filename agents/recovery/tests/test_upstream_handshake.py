from __future__ import annotations

from agents.recovery.adapters.prep_adapter import adapt_prep
from agents.recovery.adapters.receiving_adapter import adapt_receiving
from agents.recovery.adapters.returns_adapter import adapt_returns
from agents.recovery.adapters.fee_report_adapter import adapt_fee_report
from agents.recovery.adapters import flatten_checks
import pytest

from agents.recovery.domain.validation import RecoveryInputError


def test_previous_evidence_is_preserved_through_adapters() -> None:
    previous = [{"manager": "upstream", "unit_id": "U-1", "org_id": "org-a"}]
    fee = adapt_fee_report(
        "line_id,report_type,unit_id,org_id,sku,fnsku,fba_shipment_id,order_id,charge_type,quantity,amount_usd,posted_date\n"
        "F-1,fee_report,U-1,org-a,sku-1,fnsku-1,S-1,O-1,inbound_defect_fee,1,4.25,2026-06-01\n"
    )
    prep = adapt_prep(
        "record_id,unit_id,org_id,captured_at,photo_refs,polybag_present_sealed\nP-1,U-1,org-a,2026-06-01T00:00:00Z,,sealed\n",
        [*previous, *fee],
    )
    receiving = adapt_receiving(
        "record_id,unit_id,org_id,captured_at,identity_match,qty_ordered,qty_received\nR-1,U-1,org-a,2026-06-01T00:00:00Z,yes,2,2\n",
        prep,
    )
    returns = adapt_returns(
        "record_id,unit_id,org_id,captured_at,identity_match,operator_disposition,observed_state\nT-1,U-1,org-a,2026-06-01T00:00:00Z,yes,restock,opened_unused\n",
        receiving,
    )
    assert [item["manager"] for item in returns] == ["upstream", "fee_report", "prep", "receiving", "returns"]
    assert all(item["org_id"] == "org-a" and item["unit_id"] == "U-1" for item in returns)
    assert returns[2]["attributed_charge_id"] == "F-1"
    assert returns[-1]["observations"]["completeness_verified"] == "uncertain"
    assert all(check["attributed_charge_id"] == "F-1" for check in flatten_checks([returns[2]]))


def test_same_unit_in_another_org_does_not_link_to_fee_line() -> None:
    fee = adapt_fee_report(
        "line_id,report_type,unit_id,org_id,sku,fnsku,fba_shipment_id,order_id,charge_type,quantity,amount_usd,posted_date\n"
        "F-1,fee_report,U-1,org-a,sku-1,fnsku-1,S-1,O-1,inbound_defect_fee,1,4.25,2026-06-01\n"
    )
    records = adapt_prep(
        "record_id,unit_id,org_id,captured_at,photo_refs,polybag_present_sealed\nP-1,U-1,org-b,2026-06-01T00:00:00Z,,sealed\n",
        fee,
    )
    assert records[-1]["attributed_charge_ids"] == []
    assert all(check["attributed_charge_id"] is None for check in records[-1]["checks"])


def test_non_fee_rows_remain_unresolved_ledger_candidates() -> None:
    rows = adapt_fee_report(
        "line_id,report_type,unit_id,org_id,sku,fnsku,fba_shipment_id,order_id,charge_type,quantity,amount_usd,posted_date\n"
        "C-1,reimbursement_report,U-1,org-a,sku-1,F-1,S-1,O-1,reimbursement,1,4.25,2026-06-01\n"
    )
    assert rows[0]["line_kind"] == "unresolved_ledger_candidate"
    assert "charge_id" not in rows[0]


def test_fee_amount_with_subcent_precision_is_rejected() -> None:
    with pytest.raises(RecoveryInputError):
        adapt_fee_report(
            "line_id,report_type,unit_id,org_id,sku,fnsku,fba_shipment_id,order_id,charge_type,quantity,amount_usd,posted_date\n"
            "F-1,fee_report,U-1,org-a,sku-1,F-1,S-1,O-1,inbound_defect_fee,1,4.250,2026-06-01\n"
        )