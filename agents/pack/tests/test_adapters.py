from __future__ import annotations
from pathlib import Path
from agents.pack.adapters.order_adapter import extract_expected_order, parse_order_document
from agents.pack.adapters.prep_adapter import inspect_prep_gate
from agents.pack.core.agent import handle


def test_order_adapter_extracts_from_context():
    req = {
        "context": {
            "order_lines": [{"sku": "SKU-TEST-1", "quantity": 2, "name": "Item One"}]
        }
    }
    extracted = extract_expected_order(req)
    assert len(extracted) == 1
    assert extracted[0]["sku"] == "SKU-TEST-1"
    assert extracted[0]["quantity"] == 2


def test_prep_adapter_returns_none_when_no_prep_evidence():
    req = {"previous_evidence": [{"stage": "receiving", "record_id": "RCV-1"}]}
    assert inspect_prep_gate(req) is None


def test_prep_adapter_inspects_allow_gate():
    prep_ev = {
        "stage": "prep",
        "record_id": "PRP-001",
        "decision": {"verdict": "PASS"},
        "payload": {"gate_status": "ALLOW", "ready_for_pack": True, "sku": "SKU-A"},
    }
    gate = inspect_prep_gate({"previous_evidence": [prep_ev]})
    assert gate is not None
    assert gate["gate_status"] == "ALLOW"
    assert gate["ready_for_pack"] is True
    assert gate["overall_verdict"] == "PASS"


def test_prep_adapter_inspects_hold_gate():
    prep_ev = {
        "stage": "prep",
        "record_id": "PRP-002",
        "decision": {"verdict": "FAIL"},
        "payload": {"gate_status": "HOLD", "ready_for_pack": False},
    }
    gate = inspect_prep_gate({"previous_evidence": [prep_ev]})
    assert gate is not None
    assert gate["gate_status"] == "HOLD"
    assert gate["ready_for_pack"] is False


def test_handle_respects_prep_hold_gate():
    prep_ev = {
        "stage": "prep",
        "record_id": "PRP-002",
        "decision": {"verdict": "FAIL"},
        "payload": {"gate_status": "HOLD", "ready_for_pack": False},
    }
    req = {
        "schema_version": "1.0",
        "request_id": "WF-org_demo_alpha-UNIT-0001:pack",
        "workflow_id": "WF-org_demo_alpha-UNIT-0001",
        "stage": "pack",
        "subject": {"org_id": "org_demo_alpha", "subject_id": "UNIT-0001", "route": "fba"},
        "inputs": [],
        "previous_evidence": [prep_ev],
        "context": {"order_lines": [{"sku": "SKU-1", "quantity": 1}]},
    }
    out = handle(req)
    assert out["verdict"] == "UNCERTAIN"
    assert out["status"] == "pending"
    assert "Prep gate is HOLD" in out["next_step_recommendation"]["reason"]
