from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from agents.recovery.config import RecoverySettings
from agents.recovery.domain.assessment import project_contract_verdict
from agents.recovery.domain.canonical import Charge, ContractEvidence, RecoveryRule, Reimbursement
from agents.recovery.domain.ledger import InternalDecisionFacts
from agents.recovery.fail_open import fail_open_boundary
from agents.recovery.tenancy import tenant_scope
from shared.utils import sample_data
from shared.utils.records import build_output, build_record, check, utcnow
from shared.utils.server import make_app
from shared.utils.stubs import STUB_MODEL, effective_verdict, previous

STAGE = "recovery"
AGENT_ID = "recovery-stub@0"


def position(line: dict, request: dict) -> tuple[str, str, list[str]]:
    """(CONTRADICTS | SUPPORTS | SILENT, detail, evidence record ids). Uses EFFECTIVE verdicts (overrides applied)."""
    ctype = line.get("charge_type", "")
    if ctype == "inbound_defect_fee":
        prep = previous(request, "prep")
        if not prep or prep.get("status") != "completed":
            return "SILENT", "no usable Prep record for this subject", []
        v = effective_verdict(request, prep)
        if v == "PASS":
            return "CONTRADICTS", "Prep evidence shows the unit compliant", [prep["record_id"]]
        if v == "FAIL":
            return "SUPPORTS", "Prep evidence shows a defect", [prep["record_id"]]
        return "SILENT", "Prep evidence is uncertain", [prep["record_id"]]
    if ctype == "refund_issued_item_not_returned":
        ret = previous(request, "returns")
        if ret and ret.get("status") == "completed" and ret.get("checks") and ret["checks"][0]["verdict"] == "PASS":
            return "CONTRADICTS", "Returns record shows the right item came back", [ret["record_id"]]
        return "SILENT", "no usable Returns record", []
    if ctype == "fulfilment_fee_weight_tier":
        return "SILENT", "no measured weight/dimensions upstream (finding F-07)", []
    if ctype == "lost_inbound":
        return "SILENT", "receiving shortfall is supplier-side, not channel-side loss (finding F-10)", []
    return "SILENT", f"no rule for {ctype}", []


def _handle_domain_charge(request: dict[str, Any]) -> dict[str, object]:
    settings = RecoverySettings.from_env()
    org_id = request.get("org_id")
    with tenant_scope(org_id, settings.allowed_orgs):
        charge = Charge.from_mapping(request["charge"])
        credits = tuple(Reimbursement.from_mapping(item) for item in request.get("credits", []))
        evidence = tuple(ContractEvidence.from_mapping(item) for item in request.get("evidence", []))
        rule = RecoveryRule.from_mapping(request["rule"])
        raw_facts = request["internal_facts"]
        facts = InternalDecisionFacts(
            economic_state_known=raw_facts["economic_state_known"],
            current=raw_facts["current"],
            remaining_actionable=Decimal(str(raw_facts["remaining_actionable"])),
            active_pursuit=Decimal(str(raw_facts["active_pursuit"])),
        )
        if not isinstance(facts.economic_state_known, bool) or not isinstance(facts.current, bool):
            raise ValueError("trusted engine flags must be boolean")
        if not facts.remaining_actionable.is_finite() or not facts.active_pursuit.is_finite():
            raise ValueError("trusted engine amounts must be finite decimals")
        if facts.remaining_actionable < 0 or facts.active_pursuit < 0:
            raise ValueError("trusted engine amounts must be non-negative")
        decision = project_contract_verdict(
            charge,
            credits,
            evidence,
            rule,
            facts,
            date.fromisoformat(request["evaluated_on"]) if request.get("evaluated_on") else date.today(),
        )
        return {
            "verdict": decision.verdict,
            "position": decision.position,
            "reason": decision.reason,
            "remaining_amount": str(decision.remaining_amount) if decision.remaining_amount is not None else None,
            "currency": decision.currency,
            "status": "complete",
        }


def _handle_contract_workflow(request: dict[str, Any]) -> dict[str, Any]:
    s = request["subject"]
    org_id = s.get("org_id", "")
    subject_id = s.get("subject_id", "")
    settings = RecoverySettings.from_env()

    # Tenancy verification: must refuse (raise LookupError) cross-tenant or unknown subjects
    if org_id not in settings.allowed_orgs or not sample_data.has("receiving", subject_id, org_id):
        raise LookupError(f"unknown subject {subject_id} in {org_id}")

    lines = sample_data.fee_lines(subject_id, org_id)
    checks, charges, claimable = [], [], 0.0
    for line in lines:
        pos, why, ids = position(line, request)
        try:
            amount = float(line.get("amount_usd", 0.0))
        except (ValueError, TypeError):
            amount = 0.0
        if pos == "CONTRADICTS" and amount <= 0:
            pos, why = "SILENT", "amount is 0.00: nothing to claim, or the amount is missing (finding F-09)"
        verdict = {"CONTRADICTS": "FAIL", "SUPPORTS": "PASS", "SILENT": "UNCERTAIN"}[pos]
        line_key = f"charge_{line['line_id'].lower().replace('-', '_')}"
        checks.append(
            check(
                line_key,
                verdict,
                None,
                expected="charge supported by evidence",
                observed=pos,
                detail=why,
                evidence_refs=ids,
                uncertain_reason="insufficient_evidence",
            )
        )
        if pos == "CONTRADICTS":
            claimable += amount
        charges.append({
            "line_id": line["line_id"],
            "charge_type": line["charge_type"],
            "amount_usd": amount,
            "position": pos,
            "reason": why,
            "evidence_record_ids": ids,
        })

    claim = any(c["position"] == "CONTRADICTS" for c in charges)
    silent = any(c["position"] == "SILENT" for c in charges)
    overall_verdict = "FAIL" if claim else ("UNCERTAIN" if silent else "PASS")
    outcome = "claim_recommended" if claim else ("insufficient_evidence" if silent else "no_claim")

    captured_at = max((l["posted_date"] + "T00:00:00Z" for l in lines if l.get("posted_date")), default=utcnow())
    record = build_record(
        request,
        agent_id=AGENT_ID,
        record_id=f"RCY-{subject_id}",
        model=STUB_MODEL,
        captured_at=captured_at,
        checks=checks,
        outcome=outcome,
        verdict=overall_verdict,
        needs_human=False,
        reason=f"Recovery audit: {len(charges)} charge(s), {sum(c['position'] == 'CONTRADICTS' for c in charges)} contradicted",
        payload={
            "charges": charges,
            "claimable_usd": round(claimable, 2),
            "unclaimable": [c for c in charges if c["position"] != "CONTRADICTS"],
        },
    )
    return build_output(record, next_step="complete")


def handle(request: dict[str, Any]) -> dict[str, Any]:
    if "charge" in request:
        return fail_open_boundary(_handle_domain_charge)(request)
    return _handle_contract_workflow(request)


app = make_app(STAGE, handle)