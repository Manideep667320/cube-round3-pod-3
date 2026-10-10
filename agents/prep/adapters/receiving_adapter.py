"""Receiving Adapter: Maps Agent 01's RCV-XXXX payload into Prep WorkOrder."""
from typing import Any
from agents.prep.schemas import WorkOrder
from shared.utils import sample_data


def map_to_work_order(request: dict[str, Any]) -> WorkOrder:
    """Translates an AgentInput request and its previous Receiving evidence into a WorkOrder."""
    subject = request.get("subject", {})
    unit_id = subject.get("subject_id", "UNIT-0001")
    org_id = subject.get("org_id", "org_demo_alpha")

    # Ingest from previous evidence if present
    prev_ev = request.get("previous_evidence", [])
    rcv = next((ev for ev in prev_ev if ev.get("stage") == "receiving"), None)
    rcv_refs = rcv.get("refs", {}) if rcv else {}
    rcv_payload = rcv.get("payload", {}) if rcv else {}
    vp = rcv_payload.get("visual_perception") or request.get("context", {}).get("case", {}).get("visual_perception")
    detected_sku = (vp.get("sku") if vp else None) or rcv_refs.get("sku") or rcv_payload.get("sku")

    # Extract sample baseline fields if available
    row = sample_data.row("prep", unit_id, org_id) if sample_data.has("prep", unit_id, org_id) else {}

    return WorkOrder(
        work_order_id=row.get("work_order_id", f"WO-{unit_id}"),
        unit_id=unit_id,
        org_id=org_id,
        fba_shipment_id=row.get("fba_shipment_id", f"FBA-{unit_id}"),
        sku=detected_sku or row.get("sku", "SKU-UNKNOWN"),
        asin=rcv_refs.get("asin") or row.get("asin", "B0UNKNOWN"),
        fnsku=row.get("fnsku", "X0UNKNOWN"),
        prep_price_usd=float(row.get("prep_price_usd", 0.75)),
        wo_polybag=row.get("polybag_present_sealed") != "not_required",
        wo_suffocation_warning=row.get("suffocation_warning") != "not_required",
        wo_expiry_date=row.get("expiry_date") != "not_required" if "expiry_date" in row else False,
        wo_handling_marks=row.get("handling_marks", "") if row.get("handling_marks") != "not_required" else ""
    )

ingest_receiving_evidence = map_to_work_order
