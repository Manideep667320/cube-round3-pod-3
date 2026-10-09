"""Prep Adapter: Ingests Prep stage cartonization manifest & gate status (Agent 02 -> Agent 03)."""
from __future__ import annotations

from typing import Any


def inspect_prep_gate(request: dict[str, Any]) -> dict[str, Any] | None:
    """Extracts Prep cartonization manifest & gate status if Prep ran upstream.

    Returns:
        dict with gate_status ('ALLOW' | 'HOLD'), ready_for_pack (bool), sku, and verdict,
        or None if no Prep evidence is present (standard for MFN routes).
    """
    prior = request.get("previous_evidence") or []
    prep_records = [r for r in prior if r.get("stage") == "prep"]
    if not prep_records:
        return None

    prep_ev = prep_records[-1]
    payload = prep_ev.get("payload") or {}
    decision = prep_ev.get("decision") or {}
    verdict = decision.get("verdict", "UNCERTAIN")

    gate_status = payload.get("gate_status") or ("ALLOW" if verdict == "PASS" else "HOLD")
    ready_for_pack = payload.get("ready_for_pack", verdict == "PASS")

    refs = prep_ev.get("subject", {}).get("refs") or prep_ev.get("refs") or {}
    sku = refs.get("sku") or payload.get("sku")
    fnsku = refs.get("fnsku") or payload.get("fnsku")

    return {
        "record_id": prep_ev.get("record_id"),
        "overall_verdict": verdict,
        "ready_for_pack": bool(ready_for_pack),
        "gate_status": gate_status,
        "sku": sku,
        "fnsku": fnsku,
    }
