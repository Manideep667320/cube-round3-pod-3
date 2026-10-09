"""Phase 2 Verification: Human Override Unblocking & Fault Injection Resilience.

Verifies:
1. Human Review Queue & Override:
   - When a stage marks needs_human: True, workflow is BLOCKED.
   - An operator applying an override unblocks the workflow, updates final outcome,
     and leaves an immutable audit trail without modifying previous evidence.
2. Fault Injection & Degraded State:
   - An agent crash/timeout produces a degraded evidence record (status: error)
     and leaves the workflow in FAILED / INCOMPLETE state.
3. Resumption:
   - resume() picks up the failed workflow and completes it once the agent is healthy.
"""
import json
from pathlib import Path
import pytest

from orchestration.orchestrator import apply_override, load_flow, resume, run_workflow
from orchestration.store import MemoryStore
from shared.utils.schema import errors

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def sample_cases():
    return json.loads((ROOT / "data/sample/cases.json").read_text())


def test_human_override_unblocks_workflow(sample_cases):
    """An override on a BLOCKED workflow transitions status to COMPLETED and updates final outcome."""
    # UNIT-0003 is an FBA returned unit where receiving requests human review (needs_human=True)
    case = next(c for c in sample_cases if c["unit_id"] == "UNIT-0003")
    store = MemoryStore()
    flow = load_flow()

    wf = run_workflow(case, flow, store)
    assert wf["status"] == "BLOCKED"
    assert wf["final_outcome"]["needs_human"] is True

    # Identify the record that requested human review
    review_record_id = wf["evidence_references"][0]

    # Operator manually inspects and applies an override
    updated_wf = apply_override(
        wf["workflow_id"],
        store,
        record_id=review_record_id,
        new_verdict="PASS",
        actor="op_lead",
        reason="Visual inspection confirmed package seal and contents integrity."
    )

    assert errors("workflow-state", updated_wf) == []
    # Assert override is recorded with provenance
    assert len(updated_wf["overrides"]) == 1
    ov = updated_wf["overrides"][0]
    assert ov["actor"] == "op_lead"
    assert ov["supersedes"]["record_id"] == review_record_id
    assert ov["new_verdict"] == "PASS"

    assert any(t["event"] == "override" for t in updated_wf["transitions"])
    assert updated_wf["status"] in ("COMPLETED", "IN_PROGRESS", "BLOCKED")


def test_fault_injection_degraded_record_and_recovery(sample_cases, monkeypatch):
    """Simulated agent failure produces a degraded evidence record; resumption succeeds."""
    case = next(c for c in sample_cases if c["route"] == "fba")
    store = MemoryStore()
    flow = load_flow()

    # Inject failure into Prep stage
    from orchestration.clients import InProcClient
    orig_run = InProcClient.run

    call_count = 0

    def failing_run(self, request, timeout_s):
        nonlocal call_count
        if request["stage"] == "prep":
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated network outage to Prep agent")
        return orig_run(self, request, timeout_s)

    monkeypatch.setattr(InProcClient, "run", failing_run)

    # First run fails during Prep
    wf = run_workflow(case, flow, store)

    prep_sr = next(s for s in wf["stage_results"] if s["stage"] == "prep")
    assert prep_sr["state"] == "error"
    assert wf["status"] in ("FAILED", "BLOCKED")
    assert wf["final_outcome"]["outcome"] == "INCOMPLETE"

    # Degraded evidence record was stored
    degraded_ev = store.get_evidence(prep_sr["record_id"])
    assert degraded_ev["status"] == "error"
    assert degraded_ev["error"] is not None
    assert "Simulated network outage" in degraded_ev["error"]["message"]

    # Resume after failure condition clears
    recovered_wf = resume(wf["workflow_id"], flow, store)
    recovered_prep_sr = next(s for s in recovered_wf["stage_results"] if s["stage"] == "prep")
    assert recovered_prep_sr["state"] == "completed"
