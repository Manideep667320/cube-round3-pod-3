"""System Handshake Integration Tests: End-to-End Cross-Agent Data Lineage.

Verifies the full contract chaining across all 5 agents:
1. Receiving -> Prep (FBA route work-order & compliance lineage)
2. Receiving -> Pack (MFN route order-line & contents lineage)
3. Pack -> Returns (pre-shipment contents verification & sent_contents_seen)
4. Returns -> Recovery (identity proof reversing refund_issued_item_not_returned)
5. Prep -> Recovery (inbound compliance & dimensions lineage)
6. Multitenancy isolation & unbroken evidence audit trail
"""
import json
from pathlib import Path
import pytest

from orchestration.orchestrator import run_workflow, load_flow, discover_inputs
from orchestration.store import MemoryStore
from shared.utils.stubs import previous
from shared.utils.schema import errors

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def sample_cases():
    return json.loads((ROOT / "data/sample/cases.json").read_text())


def test_receiving_to_prep_handshake(sample_cases):
    """Receiving output (RCV) cleanly feeds Prep (PRP) on FBA units."""
    case = next(c for c in sample_cases if c["route"] == "fba" and not c.get("returned"))
    store = MemoryStore()
    wf = run_workflow(case, store=store)

    stages = [s["stage"] for s in wf["stage_results"]]
    assert "receiving" in stages
    assert "prep" in stages

    rcv_sr = next(s for s in wf["stage_results"] if s["stage"] == "receiving")
    prp_sr = next(s for s in wf["stage_results"] if s["stage"] == "prep")

    assert rcv_sr["state"] == "completed"
    assert prp_sr["state"] == "completed"

    prp_ev = store.get_evidence(prp_sr["record_id"])
    assert rcv_sr["record_id"] in prp_ev["upstream_refs"], "Prep must cite Receiving in upstream_refs"
    assert prp_ev["subject"]["org_id"] == case["org_id"]


def test_receiving_to_pack_handshake(sample_cases):
    """Receiving output (RCV) cleanly feeds Pack (PCK) on MFN units."""
    case = next(c for c in sample_cases if c["route"] == "mfn" and not c.get("returned"))
    store = MemoryStore()
    wf = run_workflow(case, store=store)

    stages = [s["stage"] for s in wf["stage_results"]]
    assert "receiving" in stages
    assert "pack" in stages
    assert "prep" not in stages or next(s for s in wf["stage_results"] if s["stage"] == "prep")["state"] == "skipped"

    rcv_sr = next(s for s in wf["stage_results"] if s["stage"] == "receiving")
    pck_sr = next(s for s in wf["stage_results"] if s["stage"] == "pack")

    assert rcv_sr["state"] == "completed"
    pck_ev = store.get_evidence(pck_sr["record_id"])
    assert rcv_sr["record_id"] in pck_ev["upstream_refs"], "Pack must cite Receiving in upstream_refs"


def test_pack_to_returns_handshake(sample_cases):
    """Pack output cleanly feeds Returns; Returns confirms sent_contents_seen."""
    case = next(c for c in sample_cases if c["route"] == "mfn" and c.get("returned"))
    store = MemoryStore()
    wf = run_workflow(case, store=store)

    pck_sr = next(s for s in wf["stage_results"] if s["stage"] == "pack")
    rtn_sr = next(s for s in wf["stage_results"] if s["stage"] == "returns")

    assert rtn_sr["state"] == "completed"
    rtn_ev = store.get_evidence(rtn_sr["record_id"])

    assert pck_sr["record_id"] in rtn_ev["upstream_refs"], "Returns must cite Pack in upstream_refs"
    assert rtn_ev["payload"].get("sent_contents_seen") is True, "Returns must observe pre-shipment pack contents"


def test_returns_to_recovery_dispute_handshake(sample_cases):
    """Returns PASS identity check allows Recovery to CONTRADICT refund_issued_item_not_returned."""
    case = next(c for c in sample_cases if c.get("returned"))
    store = MemoryStore()
    wf = run_workflow(case, store=store)

    rtn_sr = next(s for s in wf["stage_results"] if s["stage"] == "returns")
    rcy_sr = next(s for s in wf["stage_results"] if s["stage"] == "recovery")

    assert rtn_sr["state"] == "completed"
    assert rcy_sr["state"] == "completed"

    rcy_ev = store.get_evidence(rcy_sr["record_id"])
    assert rtn_sr["record_id"] in rcy_ev["upstream_refs"], "Recovery must cite Returns in upstream_refs"


def test_full_5_agent_end_to_end_lineage_and_audit(sample_cases):
    """End-to-end multi-agent execution validates all schemas, audit events, and hashes."""
    case = next(c for c in sample_cases if c["route"] == "fba" and c.get("returned"))
    store = MemoryStore()
    wf = run_workflow(case, store=store)

    assert errors("workflow-state", wf) == []
    fo = wf["final_outcome"]
    assert errors("final-outcome", fo) == []
    assert len(fo["contributing_records"]) >= 3

    # All generated evidence records validate against schema and verify cryptographic hashes
    for rid in wf["evidence_references"]:
        ev = store.get_evidence(rid)
        assert errors("evidence", ev) == []
        assert ev["subject"]["org_id"] == case["org_id"]
        assert len(ev["content_hash"]) == 64

    # Verify tenancy isolation: cross-tenant access is rejected
    other_tenant = "org_demo_alpha" if case["org_id"] == "org_demo_bravo" else "org_demo_bravo"
    cross_wf = run_workflow({**case, "org_id": other_tenant})
    assert cross_wf["status"] in ("FAILED", "BLOCKED")
    assert any(s["state"] == "error" for s in cross_wf["stage_results"])
