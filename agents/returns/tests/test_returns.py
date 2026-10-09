"""Unit tests for Returns Manager agent."""
from __future__ import annotations

import pytest
from agents.returns.condition import classify_amazon_condition, determine_disposition
from agents.returns.engine import process_returns_request


def test_classify_amazon_condition():
    assert classify_amazon_condition("factory_sealed") == "New"
    assert classify_amazon_condition("opened_unused") == "Used - Like New"
    assert classify_amazon_condition("signs_of_use") == "Used - Very Good"
    assert classify_amazon_condition("damaged") == "Unsellable"
    assert classify_amazon_condition("opened_unused", is_damaged=True) == "Unsellable"


def test_determine_disposition():
    disp, needs_human, reason = determine_disposition("New")
    assert disp == "restock"
    assert not needs_human

    disp, needs_human, reason = determine_disposition("Used - Like New")
    assert disp == "restock"

    disp, needs_human, reason = determine_disposition("Used - Very Good")
    assert disp == "refurbish"

    disp, needs_human, reason = determine_disposition("Unsellable", missing_parts=["cable"])
    assert disp == "dispose"


def test_process_returns_request_success():
    request = {
        "schema_version": "1.0",
        "request_id": "REQ-RTN-TEST-1",
        "workflow_id": "WF-org_demo_alpha-UNIT-0014",
        "stage": "returns",
        "subject": {
            "org_id": "org_demo_alpha",
            "subject_id": "UNIT-0014",
            "unit_id": "UNIT-0014",
            "unit_scope": "unit",
            "refs": {"sku": "SKU-LAMP-LED"},
        },
        "inputs": [],
        "previous_evidence": [],
    }
    out = process_returns_request(request)
    assert out["schema_version"] == "1.0"
    assert out["stage"] == "returns"
    assert out["status"] == "completed"
    assert out["verdict"] in ("PASS", "FAIL", "UNCERTAIN")
    
    evidence = out["evidence"]
    assert evidence["payload"]["condition_graded"] is True
    assert "amazon_condition" in evidence["payload"]
    assert len(evidence["checks"]) == 3


def test_process_returns_request_cross_tenant_raises_lookup_error():
    request = {
        "schema_version": "1.0",
        "request_id": "REQ-RTN-TEST-2",
        "workflow_id": "WF-invalid-UNIT-0014",
        "stage": "returns",
        "subject": {
            "org_id": "invalid_org_tenant",
            "subject_id": "UNIT-0014",
            "unit_id": "UNIT-0014",
            "unit_scope": "unit",
        },
        "inputs": [],
        "previous_evidence": [],
    }
    with pytest.raises(LookupError):
        process_returns_request(request)
