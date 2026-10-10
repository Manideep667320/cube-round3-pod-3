"""Prep Manager: Agent entry point exposing in-process handle() and FastAPI HTTP service."""
import asyncio
from typing import Any
from agents.prep.schemas import WorkOrder
from agents.prep.service import inspect_prepped_unit
from agents.prep.tenancy import set_current_org
from agents.prep.config import settings
from shared.utils import sample_data
from shared.utils.records import build_output, build_record, check, rollup
from shared.utils.server import make_app
from shared.utils.stubs import STUB_MODEL, photos, verdict_from
from .adapters.receiving_adapter import map_to_work_order

STAGE = "prep"
AGENT_ID = "prep-manager@2.0.0"

RULE_SPECS = [
    ("polybag_sealed", "polybag_present_sealed", {"yes"}, {"not_sealed", "missing"}),
    ("suffocation_warning", "suffocation_warning", {"legible"}, {"obscured_by_fold", "missing"}),
    ("fnsku_label_placement", "fnsku_label_placement", {"flat"}, {"on_seam", "on_curve", "on_edge", "missing"}),
    ("original_barcode_covered", "original_barcode_covered", {"yes"}, {"no"}),
    ("expiry_legible", "expiry_date", {"legible"}, {"illegible_after_wrap"}),
    ("handling_marks", "handling_marks", {"all_present"}, {"some_missing"}),
]


def handle(request: dict[str, Any]) -> dict[str, Any]:
    s = request["subject"]
    org_id = s["org_id"]
    subject_id = s["subject_id"]

    # Tenancy verification
    if org_id not in settings.allowed_orgs or not sample_data.has("prep", subject_id, org_id):
        raise LookupError(f"Unauthorized or unknown subject '{subject_id}' for tenant '{org_id}'")

    set_current_org(org_id)

    # 1. Translate via receiving adapter into internal WorkOrder
    work_order: WorkOrder = map_to_work_order(request)

    # Extract photos from request or certified sample row
    sample_row = sample_data.row("prep", subject_id, org_id)
    input_photos = request.get("inputs") or photos(sample_row)
    photo_refs = [p["ref"] for p in input_photos]

    # 2. Execute authoritative Prep Manager engine (inspect_prepped_unit)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            prep_record = pool.submit(asyncio.run, inspect_prepped_unit(work_order, photo_refs)).result()
    else:
        prep_record = asyncio.run(inspect_prepped_unit(work_order, photo_refs))

    # 3. Construct schema-compliant checks
    checks = []
    checks_dict = prep_record.checks.model_dump()
    for key, col, ok, bad in RULE_SPECS:
        val = checks_dict.get(col)
        if val == "not_required" or val is None:
            continue
        v = verdict_from(val, ok, bad)
        checks.append(
            check(
                key,
                v,
                None,
                expected=sorted(ok)[0],
                observed=val,
                detail=f"Rule evaluated: {key}",
                evidence_refs=photo_refs,
                uncertain_reason="poor_image" if v == "UNCERTAIN" else None
            )
        )

    verdict = prep_record.overall_verdict if prep_record.overall_verdict in ("PASS", "FAIL", "UNCERTAIN") else rollup(checks)
    outcome = {"PASS": "compliant", "FAIL": "non_compliant", "UNCERTAIN": "pending_review"}.get(verdict, "pending_review")

    # 4. Build immutable Evidence Record
    base_rid = prep_record.record_id
    req_id = request.get("request_id", "")
    rid = f"{base_rid}-r{req_id.split(':r')[-1]}" if ":r" in req_id else base_rid

    record = build_record(
        request,
        agent_id=AGENT_ID,
        record_id=rid,
        captured_at=prep_record.captured_at,
        operator_id=prep_record.operator_id,
        refs={
            "work_order_id": prep_record.work_order_id,
            "fba_shipment_id": prep_record.fba_shipment_id,
            "sku": prep_record.sku,
            "asin": prep_record.asin,
            "fnsku": prep_record.fnsku
        },
        checks=checks,
        outcome=outcome,
        verdict=verdict,
        model={
            "name": f"prep-vlm-{settings.vlm_model}",
            "version": "2.0.0",
            "provider": settings.vlm_provider,
            "calls": 1,
            "cost_usd": 0.005,
        },
        inputs=input_photos,
        reason=f"Amazon FBA prep audit: overall={verdict}",
        payload={
            "prep_price_usd": prep_record.prep_price_usd,
            "measurements": None,
            "grounding_evidence": [g.model_dump() for g in prep_record.evidence_grounding]
        }
    )

    return build_output(record)


app = make_app(STAGE, handle)
