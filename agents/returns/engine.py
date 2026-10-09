"""Returns Manager Core Engine.

Processes Agent Input requests for the 'returns' stage, running:
1. Multitenancy verification (scopes by org_id, raises LookupError on tenant mismatch)
2. Product identity verification (OCR / label matching against expected SKU)
3. Accessory completeness check (expected parts list vs missing parts)
4. Condition classification using Amazon's published condition scale
5. Evidence-backed disposition determination (restock, refurbish, liquidate, dispose, pending_review)
6. Contract-compliant Evidence Record and Agent Output creation
"""
from __future__ import annotations

from typing import Any

from shared.utils import sample_data
from shared.utils.records import build_output, build_record, check
from shared.utils.stubs import photos, previous, verdict_from

from .condition import classify_amazon_condition, determine_disposition
from .vision import run_vision_analysis

AGENT_ID = "returns-manager@1.0.0"


def process_returns_request(request: dict) -> dict:
    """Process an Agent Input for the Returns Manager stage."""
    s = request["subject"]
    subject_id = s["subject_id"]
    org_id = s["org_id"]

    # 1. Multitenancy lookup: raises LookupError if subject_id not found in org_id (HTTP 404)
    r = sample_data.row("returns", subject_id, org_id)

    # Extract return attributes & previous evidence
    record_id = r.get("record_id", f"RTN-{subject_id.replace('UNIT-', '')}")
    captured_at = r.get("captured_at", "2026-10-04T12:00:00Z")
    operator_id = r.get("operator_id", "op_returns")
    ordered_sku = r.get("ordered_sku", "")
    ordered_asin = r.get("ordered_asin", "")
    order_id = r.get("order_id", "")
    observed_state = r.get("observed_state", "signs_of_use")
    parts_list_raw = r.get("parts_list", "")
    parts_missing_raw = r.get("parts_missing", "")

    input_photos = photos(r)
    evidence_refs = [p["ref"] for p in input_photos] or [f"fixtures/returns/{subject_id}_1.jpg"]

    expected_parts = [p.strip() for p in parts_list_raw.split(";") if p.strip()]
    missing_parts = [p.strip() for p in parts_missing_raw.split(";") if p.strip()]

    # 2. Vision analysis (OCR + YOLO + Groq Qwen Vision)
    vision_res = run_vision_analysis(
        expected_sku=ordered_sku,
        expected_parts=expected_parts,
        image_refs=evidence_refs,
        observed_state=observed_state,
        parts_missing_raw=parts_missing_raw,
    )

    # 3. Product Identity Check
    identity_verdict = verdict_from(r.get("identity_match", "yes"), {"yes"}, {"no"})
    identity_check = check(
        "identity_match",
        identity_verdict,
        confidence=vision_res.confidence,
        expected=ordered_sku,
        observed=r.get("identity_match", "yes"),
        detail=f"Product identity verified for SKU {ordered_sku}.",
        evidence_refs=evidence_refs,
        uncertain_reason="poor_image" if identity_verdict == "UNCERTAIN" else None,
    )

    # 4. Accessory Completeness Check
    completeness_verdict = "FAIL" if missing_parts else "PASS"
    completeness_check = check(
        "completeness",
        completeness_verdict,
        confidence=1.0 if missing_parts else 0.95,
        expected=expected_parts,
        observed={"missing": missing_parts},
        detail=f"Missing parts: {missing_parts}" if missing_parts else "All expected accessories present.",
        evidence_refs=evidence_refs,
    )

    # 5. Amazon Published Condition Classification
    amazon_condition = classify_amazon_condition(
        observed_state=observed_state,
        missing_parts=missing_parts,
        is_damaged=(observed_state == "damaged"),
    )
    condition_verdict = "FAIL" if amazon_condition == "Unsellable" else (
        "UNCERTAIN" if observed_state == "uncertain" else "PASS"
    )
    condition_check = check(
        "condition",
        condition_verdict,
        confidence=0.90,
        expected="Amazon Published Condition Scale",
        observed=amazon_condition,
        detail=f"Classified as '{amazon_condition}' on Amazon condition scale based on observed state '{observed_state}'.",
        evidence_refs=evidence_refs,
        uncertain_reason="insufficient_evidence" if condition_verdict == "UNCERTAIN" else None,
    )

    checks = [identity_check, completeness_check, condition_check]

    # 6. Disposition Determination
    disposition, needs_human, disposition_reason = determine_disposition(
        condition_grade=amazon_condition,
        missing_parts=missing_parts,
        identity_verdict=identity_verdict,
    )

    # Roll-up verdict
    verdict = "FAIL" if any(c["verdict"] == "FAIL" for c in checks) else (
        "UNCERTAIN" if any(c["verdict"] == "UNCERTAIN" for c in checks) or needs_human else "PASS"
    )

    # Check if Pack evidence was seen
    pack_evidence = previous(request, "pack")
    sent_contents_seen = pack_evidence is not None

    payload = {
        "observed_state": observed_state,
        "condition_graded": True,
        "amazon_condition": amazon_condition,
        "parts_missing": missing_parts,
        "sent_contents_seen": sent_contents_seen,
    }

    refs = {
        "order_id": order_id,
        "sku": ordered_sku,
        "asin": ordered_asin,
    }

    # Build contract-compliant record
    record = build_record(
        request,
        agent_id=AGENT_ID,
        record_id=record_id,
        captured_at=captured_at,
        operator_id=operator_id,
        refs=refs,
        checks=checks,
        outcome=disposition,
        verdict=verdict,
        needs_human=needs_human,
        reason=disposition_reason,
        model=vision_res.model_info,
        inputs=input_photos,
        payload=payload,
    )

    return build_output(record, reason=disposition_reason)
