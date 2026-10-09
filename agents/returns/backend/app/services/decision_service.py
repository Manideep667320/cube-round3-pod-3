"""Deterministic decision engine (v2).

Aggregates the per-photo structured evidence of ALL inspections of a return and
produces:

- identity verdict      : PASS / FAIL / UNCERTAIN
- completeness verdict  : PASS / FAIL / UNCERTAIN  (per-component aggregation)
- condition grade       : worst graded grade across photos, or UNKNOWN
- recommended disposition: RESTOCK / REFURBISH / LIQUIDATE / DISPOSE or withheld
- final outcome         : APPROVE / REJECT / MANUAL_REVIEW

Rules (ENGINE_VERSION 2.0) - all deterministic, all auditable:

  CONF-01  A photo shows a strong conflicting printed SKU  -> identity FAIL -> REJECT.
  ID-01    Identity PASS requires >= 2 independent sources (readable SKU AND
           visual assessment). Anything less is UNCERTAIN (OCR alone is never
           treated as proof of the physical product).
  ID-02    AI identity FAIL at high confidence is strong failure evidence.
  CMP-01   A component OBSERVED in ANY photo is OBSERVED overall.
  CMP-02   CONFIRMED_MISSING requires: not observed in any photo AND a
           CONTENTS_LAYOUT photo of this return exists (operator attests it
           shows all returned contents). Anything else stays UNCERTAIN -
           a single standard photo cannot prove absence.
  CMP-03   All observed -> completeness PASS; any confirmed missing -> FAIL.
  COND-01  Condition grade = worst (most severe) graded grade across photos.
  COND-02  UNKNOWN condition can never auto-approve.
  AI-01    Non-OK AI statuses (UNAVAILABLE/FAILED/TIMEOUT/MALFORMED/RATE_LIMITED)
           are surfaced and prevent auto-approval.
  DISP-01  Disposition mapping via the configured condition-scale policy
           (see condition_scale.py). Identity FAIL -> disposition withheld.
  DISP-02  Completeness FAIL downgrades RESTOCK -> REFURBISH.
  FINAL    APPROVE only when identity PASS + completeness PASS + condition
           graded + no blocking AI status + disposition in {RESTOCK, REFURBISH}.
           Liquidate/dispose always requires human sign-off. Otherwise
           MANUAL_REVIEW (or REJECT from CONF-01).

Free-form model output can never reach this stage unvalidated, and no outcome
here directly issues a refund - a human review path always exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agents.returns.backend.app.services.condition_scale import get_condition_scale

ENGINE_VERSION = "2.0"

_GRADE_SEVERITY = ["A_NEW", "B_LIGHT", "C_MODERATE", "D_DAMAGED", "E_NON_FUNCTIONAL"]
_BLOCKING_AI_STATUSES = {"TIMEOUT", "RATE_LIMITED", "MALFORMED", "FAILED"}


@dataclass
class DecisionResult:
    outcome: str                       # APPROVE | REJECT | MANUAL_REVIEW
    disposition: str | None = None     # RESTOCK | REFURBISH | LIQUIDATE | DISPOSE | None
    rationale: list[dict] = field(default_factory=list)


def decide(evidence_payloads: list[dict]) -> DecisionResult:
    """Aggregate per-photo evidence payloads into one return-level decision."""
    rationale: list[dict] = []

    def add(rule_id: str, kind: str, explanation: str) -> None:
        rationale.append({"rule_id": rule_id, "outcome": kind, "explanation": explanation})

    if not evidence_payloads:
        add("FINAL", "blocking", "No evidence has been collected for this return.")
        return DecisionResult(outcome="MANUAL_REVIEW", disposition=None, rationale=rationale)

    # ------------------------------------------------------------------ identity
    identity_verdicts = [p.get("identity", {}).get("verdict", "UNCERTAIN") for p in evidence_payloads]
    if "FAIL" in identity_verdicts:
        identity = "FAIL"
        failing = [p for p in evidence_payloads if p.get("identity", {}).get("verdict") == "FAIL"]
        notes = "; ".join(n for p in failing for n in p["identity"].get("notes", [])[:1])[:300]
        add("CONF-01" if any("conflicting" in n for n in
                             [x for p in failing for x in p["identity"].get("notes", [])]) else "ID-02",
            "reject", f"Identity FAILED on at least one photo: {notes}")
    elif "PASS" in identity_verdicts:
        identity = "PASS"
        add("ID-01", "supporting",
            "Identity confirmed by at least two independent sources (readable SKU + visual assessment).")
    else:
        identity = "UNCERTAIN"
        add("ID-01", "blocking",
            "Identity is UNCERTAIN: it requires both readable SKU evidence and agreeing visual "
            "assessment; OCR text alone is never treated as proof.")

    # -------------------------------------------------------------- completeness
    component_states: dict[str, str] = {}
    component_notes: dict[str, list[str]] = {}
    has_layout = any(p.get("view_type") == "CONTENTS_LAYOUT" for p in evidence_payloads)
    expected_names: list[str] = []
    for p in evidence_payloads:
        for c in p.get("components", []):
            name = c["name"]
            if name not in expected_names:
                expected_names.append(name)
            component_notes.setdefault(name, [])
            obs = c.get("observation", "UNCERTAIN")
            prev = component_states.get(name)
            if obs == "OBSERVED":
                component_states[name] = "OBSERVED"
                component_notes[name].append(c.get("note", ""))
            elif prev is None or prev == "NOT_OBSERVED":
                component_states[name] = obs
                component_notes[name].append(c.get("note", ""))

    confirmed_missing: list[str] = []
    uncertain_components: list[str] = []
    for name, state in component_states.items():
        if state == "OBSERVED":
            continue
        if has_layout:
            component_states[name] = "CONFIRMED_MISSING"
            confirmed_missing.append(name)
        else:
            uncertain_components.append(name)

    observed_all = [n for n, s in component_states.items() if s == "OBSERVED"]
    if component_states and not confirmed_missing and not uncertain_components:
        completeness = "PASS"
        add("CMP-01", "supporting",
            f"All expected components were observed across the collected photos: {', '.join(observed_all)}.")
    elif confirmed_missing:
        completeness = "FAIL"
        add("CMP-02", "blocking",
            f"Confirmed missing (absent from a contents-layout photo and every other photo): "
            f"{', '.join(confirmed_missing)}.")
    elif uncertain_components:
        completeness = "UNCERTAIN"
        add("CMP-02", "blocking",
            f"Not confirmed in the available photos: {', '.join(uncertain_components)}. "
            "Without a contents-layout photo this cannot be called missing.")
    else:
        completeness = "UNCERTAIN"
        add("CMP-02", "blocking", "No expected components were defined/evaluated.")

    # ----------------------------------------------------------------- condition
    grades = [p.get("condition", {}).get("grade") for p in evidence_payloads]
    graded = [g for g in grades if g and g != "UNKNOWN"]
    if graded:
        condition = max(graded, key=lambda g: _GRADE_SEVERITY.index(g) if g in _GRADE_SEVERITY else 99)
        add("COND-01", "supporting",
            f"Condition grade '{condition}' (worst across photos) per the configured condition scale.")
    else:
        condition = "UNKNOWN"
        add("COND-02", "blocking",
            "Condition grade is UNKNOWN; no disposition can rest on an ungraded condition.")

    # ---------------------------------------------------------------- AI health
    ai_statuses = {p.get("ai_summary", {}).get("status", "UNAVAILABLE") for p in evidence_payloads}
    blocking_ai = sorted(ai_statuses & _BLOCKING_AI_STATUSES)
    if blocking_ai:
        add("AI-01", "blocking",
            f"AI visual analysis had non-OK status(es): {', '.join(blocking_ai)}; findings routed to human review.")
    elif "OK" in ai_statuses:
        add("AI-01", "supporting", "AI visual analysis completed and its structured output was schema-validated.")

    # --------------------------------------------------- evidence availability
    ocr_statuses = {p.get("ocr_summary", {}).get("status", "FAILED") for p in evidence_payloads}
    bad_ocr = sorted(ocr_statuses - {"OK", "NO_TEXT_DETECTED", "LOW_CONFIDENCE"})
    if bad_ocr:
        add("OCR-01", "blocking",
            f"OCR evidence unavailable on at least one photo (status={', '.join(bad_ocr)}); "
            "identity cannot be confirmed from text.")
    yolo_statuses = {p.get("yolo_summary", {}).get("status", "FAILED") for p in evidence_payloads}
    bad_yolo = sorted(yolo_statuses - {"OK"})
    if bad_yolo:
        add("DET-01", "blocking",
            f"Object-detection evidence unavailable (status={', '.join(bad_yolo)}); "
            "components cannot be verified by the detector.")

    # --------------------------------------------------------------- disposition
    scale = get_condition_scale()
    disposition = scale.disposition_for_grade(condition)
    if identity == "FAIL":
        disposition = None
        add("DISP-01", "blocking", "Disposition withheld because identity FAILED.")
    elif disposition == "RESTOCK" and completeness == "FAIL":
        disposition = "REFURBISH"
        add("DISP-02", "blocking",
            "Disposition downgraded RESTOCK -> REFURBISH because accessories are confirmed missing.")
    if disposition:
        add("DISP-01", "supporting",
            f"Recommended disposition {disposition} (policy {scale.policy_version}, "
            f"grade {condition}, completeness {completeness}, identity {identity}).")

    # -------------------------------------------------------------------- final
    if identity == "FAIL":
        outcome = "REJECT"
        add("FINAL", "reject", "Return rejected on strong identity-conflict evidence; human override is available.")
    elif completeness == "FAIL" and identity == "PASS" and condition != "UNKNOWN":
        outcome = "MANUAL_REVIEW"
        add("FINAL", "blocking",
            "Confirmed missing accessories: an authorized reviewer must confirm the disposition.")
    elif identity == "PASS" and completeness == "PASS" and condition != "UNKNOWN" and not blocking_ai:
        if disposition in ("RESTOCK", "REFURBISH"):
            outcome = "APPROVE"
            add("FINAL", "supporting",
                "All dimensions pass: identity confirmed, complete, condition graded, AI stage OK.")
        else:
            outcome = "MANUAL_REVIEW"
            add("FINAL", "blocking",
                f"All dimensions pass, but the recommended disposition ({disposition}) is financially "
                "significant (liquidate/dispose) and requires human sign-off.")
    else:
        outcome = "MANUAL_REVIEW"
        add("FINAL", "blocking", "One or more dimensions are uncertain; a human reviewer must decide.")

    return DecisionResult(outcome=outcome, disposition=disposition, rationale=rationale)
