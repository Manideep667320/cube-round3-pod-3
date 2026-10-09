from __future__ import annotations
import csv, json, os
from pathlib import Path
from typing import Any
from shared.utils.records import build_output, build_record, check
from .verifier import expected_from_any, verify_pack
from ..vision.observer import observe, VisionError

STAGE="pack"; AGENT_ID=os.getenv("PACK_AGENT_ID","pack-manager@3.0.0"); MODEL=os.getenv("PACK_MODEL","gpt-4.1-mini"); ROOT=Path(__file__).resolve().parents[3]

def _input_root(): return Path(os.getenv("INPUT_DIR",ROOT/"data"/"input"))
def _sample_org(unit_id):
    p=ROOT/"data"/"sample"/"cases.json"
    if not p.exists(): return None
    try:
        return next((r.get("org_id") for r in json.loads(p.read_text()) if r.get("unit_id")==unit_id),None)
    except Exception: return None

def _guard_tenant(request):
    s=request["subject"]; expected=_sample_org(s["subject_id"])
    if expected and expected != s["org_id"]: raise LookupError(f"subject {s['subject_id']} does not belong to {s['org_id']}")

def _parse_document(path):
    try:
        if path.suffix.lower()==".json": return expected_from_any(json.loads(path.read_text()))
        if path.suffix.lower()==".csv":
            with path.open(newline="") as fh: return [dict(r) for r in csv.DictReader(fh)]
    except Exception: pass
    return []

def _expected_from_request(request):
    ctx=request.get("context") or {}
    for src in (ctx,ctx.get("case") or {}):
        for key in ("order_lines","expected_items","items"):
            got=expected_from_any(src.get(key));
            if got: return got
    for item in request.get("inputs") or []:
        p=Path(str(item.get("ref","")))
        for candidate in (p,_input_root()/p,ROOT/p):
            if candidate.is_file() and candidate.suffix.lower() in {".json",".csv"}:
                got=_parse_document(candidate)
                if got: return got
    for ev in reversed(request.get("previous_evidence") or []):
        got=expected_from_any((ev.get("payload") or {}).get("order_lines"))
        if got: return got
    return []

def _record(request, checks, *, outcome, reason, model, status="completed", verdict=None, confidence=None, needs_human=None, payload=None):
    prior=request.get("previous_evidence") or []
    captured=next((x.get("captured_at") for x in prior if x.get("captured_at")),"1970-01-01T00:00:00Z")
    rid="PCK-"+request["request_id"].replace(":","-")
    rec=build_record(request,agent_id=AGENT_ID,record_id=rid,captured_at=captured,checks=checks,outcome=outcome,reason=reason,model=model,status=status,inputs=list(request.get("inputs") or []),payload=payload or {},upstream_refs=[r["record_id"] for r in prior],verdict=verdict,confidence=confidence,needs_human=needs_human)
    return rec

def _uncertain(request, reason, model=None):
    refs=[x["ref"] for x in request.get("inputs") or []]
    rec=_record(request,[check("pack_observation","UNCERTAIN",None,detail=reason,evidence_refs=refs,uncertain_reason="insufficient_evidence")],outcome="pending_review",reason=reason,model=model or {"name":MODEL,"version":MODEL,"provider":"openai","calls":0,"cost_usd":None},status="pending",verdict="UNCERTAIN",needs_human=True)
    return build_output(rec,next_step="review",reason=reason)

def handle(request):
    if request.get("stage") != STAGE: raise ValueError("stage must be pack")
    _guard_tenant(request)
    expected=_expected_from_request(request)
    if not expected: return _uncertain(request,"No trusted order lines were supplied to Pack; refusing to invent expected contents.")
    images=[x for x in request.get("inputs",[]) if x.get("kind")=="image" or str(x.get("ref","")).lower().endswith((".jpg",".jpeg",".png",".webp"))]
    try: observed,model=observe(images,expected,model=MODEL,input_root=_input_root())
    except Exception as exc: return _uncertain(request,f"model_error: {type(exc).__name__}: {exc}")
    result=verify_pack(expected,observed); refs=[x["ref"] for x in request.get("inputs") or []]; checks=[]
    if result["uncertain_identity"]: checks.append(check("items_present","UNCERTAIN",None,expected=result["expected"],observed=result["observed"],detail=f"Could not confidently identify: {result['uncertain_identity']}",evidence_refs=refs,uncertain_reason="insufficient_evidence"))
    else: checks.append(check("items_present","FAIL" if result["missing"] else "PASS",None,expected=result["expected"],observed=result["observed"],detail=f"Missing: {result['missing']}" if result["missing"] else "All expected item identities are present.",evidence_refs=refs))
    checks.append(check("quantities_correct","FAIL" if result["missing"] or not result["quantities_ok"] else "PASS",None,expected=result["expected"],observed=result["observed"],detail="Expected and observed quantities differ." if not result["quantities_ok"] else "Quantities match.",evidence_refs=refs))
    checks.append(check("no_extra_items","FAIL" if result["extra"] else "PASS",None,expected={},observed=result["extra"],detail=f"Unexpected items: {result['extra']}" if result["extra"] else "No extra items observed.",evidence_refs=refs))
    verdict="FAIL" if any(c["verdict"]=="FAIL" for c in checks) else ("UNCERTAIN" if any(c["verdict"]=="UNCERTAIN" for c in checks) else "PASS")
    outcome={"PASS":"seal","FAIL":"stop_and_fix","UNCERTAIN":"pending_review"}[verdict]
    confs=[x.get("confidence") for x in observed if isinstance(x,dict) and isinstance(x.get("confidence"),(int,float))]; confidence=min(confs) if confs else None
    rec=_record(request,checks,outcome=outcome,reason=f"Pack verification result: {outcome}.",model=model,verdict=verdict,confidence=confidence,needs_human=verdict=="UNCERTAIN",payload={"observed_in_box":observed,"expected_order":expected,"verification":result})
    return build_output(rec,next_step={"PASS":"continue","FAIL":"route_to_recovery","UNCERTAIN":"review"}[verdict])
