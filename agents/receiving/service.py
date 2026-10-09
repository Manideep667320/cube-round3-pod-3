"""Service layer: ONE evaluation pipeline shared by handle() (orchestrator) and the UI API.

Contract decisions made in review (blockers B2-B6):
- decision.verdict = rollup(checks) - never a vocabulary the schema forbids
  (PASS/FAIL/UNCERTAIN). The plan's 4-state physical vocabulary
  (ACCEPT/QUARANTINE/REJECT/ESCALATE) lives in decision.outcome + payload.reasons
  and on the receivings row for the UI.
- a check is emitted ONLY when it was actually judged; rollup of judged checks is
  the verdict, so checks and decision can never contradict each other.
- record_id is deterministic from request_id (idempotency: same request in, same
  record_id out). The stored record is returned on replay; findings that genuinely
  changed get a suffixed record_id (contract: different content, different id).
- tenancy: every lookup is org-scoped; a miss raises LookupError (404 / AgentRejected).
- fail-open: unexpected errors become pending_output, never an exception (fixes the
  in-process fail-open gap from the review).
"""
from __future__ import annotations

import hashlib
import io
import json
import threading
import time
import uuid
from datetime import date

from . import coach as C
from . import config, damage, db, perception
from . import decide as D
from . import explain as E
from shared.utils.records import (add_agent_override, build_output, build_record,
                                  check as make_check, rollup, utcnow)

_SESSION_LOCK = threading.Lock()

RECEIVING_FINAL = "RECEIVING_FINAL"
RECEIVING_OVERRIDDEN = "RECEIVING_OVERRIDDEN"
OVERRIDE_REASONS = ("VISUAL_CHECK_OK", "DOC_CORRECTED", "SUPPLIER_APPROVED", "DAMAGE_CONFIRMED", "OTHER")
ROLES = ("label", "overall", "closeup")


def record_id_for(request_id: str) -> str:
    return "RCV-" + hashlib.sha256(request_id.encode()).hexdigest()[:12]


def workflow_id_for(org_id: str, subject_id: str) -> str:
    return f"WF-{org_id}-{subject_id}"


def _state_view(state: str) -> tuple[str, str]:
    """plan verdict -> (decision.outcome, next_step). The contract verdict is NOT taken
    from here: decision.verdict = rollup(checks), so checks and decision always agree."""
    _contract_verdict, outcome, next_step = D.contract_view(state)
    return outcome, next_step


# --------------------------------------------------------------------------------------
# facts: perception + damage
# --------------------------------------------------------------------------------------

def _readable(photos: list[dict]) -> list[dict]:
    out = []
    for p in photos:
        path = p.get("path")
        if not path:
            continue
        try:
            with open(path, "rb"):
                pass
        except OSError:
            continue
        out.append(p)
    return out


def gather_facts(photos: list[dict], thresholds: dict) -> dict:
    """quality + barcode from perception; damage from the VLM (with fail-safe)."""
    readable = _readable(photos)
    quality, barcode_hits = [], []
    # label first, then the order given (plan: zxing-cpp tried label first)
    ordered = sorted(readable, key=lambda p: 0 if p.get("role") == "label" else 1)
    for p in ordered:
        try:
            q, bc = perception.analyse_photo(p["path"], thresholds)
        except (OSError, ValueError):
            continue
        quality.append({"role": p.get("role"), **q})
        if bc["found"]:
            barcode_hits.append({**bc, "photo_role": p.get("role")})
    for p in readable:  # keep photo order stable for roles without analysis
        if not any(q.get("role") == p.get("role") for q in quality):
            quality.append({"role": p.get("role"), "blur": None, "glare": None,
                            "luminance": None, "flags": []})

    barcode = barcode_hits[0] if barcode_hits else {"found": False, "value": None, "format": None,
                                                    "photo_role": None}
    result = damage.assess([p["path"] for p in readable], [p["sha256"] for p in readable])
    result.pop("cached", None)  # cache bookkeeping is not a fact
    return {"barcode": barcode, "quality": quality, "damage": result,
            "photo_count": len(readable)}


# --------------------------------------------------------------------------------------
# checks: emitted only when judged
# --------------------------------------------------------------------------------------

def _uncertain_reason_for_damage(facts: dict) -> str:
    source = facts["damage"].get("source")
    if source == "unavailable":
        return "model_error"
    flags = [f for q in facts["quality"] for f in q.get("flags", [])]
    return "poor_image" if flags else "insufficient_evidence"


def build_checks(*, reasons, facts, line, qty_received, lot, expiry, thresholds, today,
                 photo_refs) -> list[dict]:
    line = line or {}
    raised = set(reasons)
    checks: list[dict] = []
    gtin = (line.get("gtin") or "").strip()

    # identity_match
    if D.NO_BARCODE in raised:
        flags = [f for q in facts["quality"] for f in q.get("flags", [])]
        reason = "poor_image" if flags else (
            "insufficient_evidence" if facts.get("photo_count", 0) == 0 else "occluded")
        checks.append(make_check(
            "identity_match", "UNCERTAIN", None,
            expected=gtin or "GTIN on the manifest line", observed="no barcode decoded",
            detail=E.TEMPLATES[D.NO_BARCODE].format(
                **{"photo_count": facts.get("photo_count", 0)}),
            evidence_refs=photo_refs, uncertain_reason=reason))
    elif D.WRONG_SKU in raised or D.NOT_IN_MANIFEST in raised:
        which = D.WRONG_SKU if D.WRONG_SKU in raised else D.NOT_IN_MANIFEST
        text = E.TEMPLATES[which].format(barcode=facts["barcode"].get("value"),
                                         expected_gtin=gtin)
        checks.append(make_check(
            "identity_match", "FAIL", None, expected=gtin,
            observed=facts["barcode"].get("value"), detail=text, evidence_refs=photo_refs))
    elif facts["barcode"].get("found") and gtin:
        checks.append(make_check(
            "identity_match", "PASS", None, expected=gtin,
            observed=facts["barcode"].get("value"), evidence_refs=photo_refs))
    # barcode found but manifest has no GTIN to compare against: not judged, omitted.

    # quantity
    if qty_received is not None and line.get("qty_expected") is not None:
        ok = int(qty_received) == int(line["qty_expected"])
        checks.append(make_check(
            "quantity", "PASS" if ok else "FAIL", None,
            expected=int(line["qty_expected"]), observed=int(qty_received),
            detail="" if ok else E.TEMPLATES[D.QTY_MISMATCH].format(
                qty_received=qty_received, qty_expected=line["qty_expected"],
                delta=int(qty_received) - int(line["qty_expected"]))))
    # lot_match (new check key; contract allows additions)
    lot_expected = (line.get("lot") or "").strip()
    lot_observed = (lot or "").strip()
    if lot_expected and lot_observed:
        ok = lot_expected == lot_observed
        checks.append(make_check(
            "lot_match", "PASS" if ok else "FAIL", None,
            expected=lot_expected, observed=lot_observed,
            detail="" if ok else E.TEMPLATES[D.LOT_CONFLICT].format(
                lot_observed=lot_observed, lot_expected=lot_expected)))
    # expiry_ok (new check key)
    expiry_value = _effective_expiry(line, expiry, today)
    if expiry_value is not None:
        expired, shown = expiry_value
        checks.append(make_check(
            "expiry_ok", "FAIL" if expired else "PASS", None,
            expected="not expired", observed=shown,
            detail=E.TEMPLATES[D.EXPIRED].format(expiry=shown, today=today.isoformat()) if expired else ""))

    # carton_damage: judged only when there were photos to judge from
    if facts.get("photo_count", 0) > 0:
        damage_fact = facts["damage"]
        th = thresholds
        conf = float(damage_fact.get("conf") or 0.0)
        severity = int(damage_fact.get("severity") or 0)
        if damage_fact.get("source") != "vlm" or conf < th["confidence_min"]:
            checks.append(make_check(
                "carton_damage", "UNCERTAIN", None, expected="none",
                observed=damage_fact.get("source", "unavailable"),
                detail=E.TEMPLATES[D.LOW_CONF_DAMAGE].format(
                    damage_source=damage_fact.get("source", "unavailable"),
                    confidence=conf, confidence_min=th["confidence_min"]),
                evidence_refs=photo_refs, uncertain_reason=_uncertain_reason_for_damage(facts)))
        else:
            bad = severity >= 2
            checks.append(make_check(
                "carton_damage", "FAIL" if bad else "PASS", round(conf, 4),
                expected="none",
                observed={"type": damage_fact.get("type"), "severity": severity},
                detail=E.TEMPLATES[D.SEVERE_DAMAGE if severity >= th["severe_damage_min"]
                                   else D.MODERATE_DAMAGE].format(
                    damage_type=damage_fact.get("type") or "unknown",
                    severity=severity, confidence=conf) if bad else "",
                evidence_refs=photo_refs))
    return checks


def _effective_expiry(line: dict, expiry: str, today: date):
    """-> (expired?, shown_value) when a date exists, else None (not judged)."""
    from .decide import _parse_date
    entered = _parse_date(expiry or "")
    expected = _parse_date((line or {}).get("expiry") or "")
    value = entered or expected
    if value is None:
        return None
    return (value < today, value.isoformat())


# --------------------------------------------------------------------------------------
# the evaluation
# --------------------------------------------------------------------------------------

def _findings_signature(record: dict, payload_keys: tuple[str, ...]) -> str:
    subset = {"checks": record["checks"], "decision": record["decision"],
              "inputs": record["inputs"], "subject": record["subject"],
              "workflow_id": record["workflow_id"],
              "payload": {k: record["payload"].get(k) for k in payload_keys}}
    return hashlib.sha256(json.dumps(subset, sort_keys=True).encode()).hexdigest()


FINDINGS_KEYS = ("reasons", "facts", "plan_verdict", "qty_received", "qty_expected",
                 "rcv_id", "attempt", "photos", "explain", "retake")


def evaluate(*, request_id: str, org_id: str, subject_id: str, line: dict | None,
             qty_received, lot: str, expiry: str, photos: list[dict], operator: str | None,
             previous_evidence: list[dict] | None = None, attempt: int = 0,
             rcv_id: str | None = None, scan_key: str | None = None,
             allow_retake: bool = False, source: str = "orchestrator") -> dict:
    """-> Agent Output (contract) for the orchestrator path and for record building.

    The UI reads the same Agent Output's evidence to render its card.
    """
    started = time.perf_counter()
    thresholds = config.thresholds()
    today = date.today()
    line = line or {}

    facts = gather_facts(photos, thresholds)
    decision = D.decide(
        facts=facts, line=line or None, qty_received=qty_received, lot=lot, expiry=expiry,
        thresholds=thresholds, today=today, manifest_gtins=db.org_gtins(org_id))
    state = decision["verdict"]
    outcome, next_step = _state_view(state)

    # retake offer: attempt 0, quarantine, and at least one retakeable reason (plan W4)
    offer = bool(allow_retake and attempt == 0 and state == D.QUARANTINE and decision["retakeable"])
    coach_obj = C.coach(decision["reasons"], facts) if offer else None

    photo_refs = [p["ref"] for p in photos if p.get("ref")]
    checks = build_checks(reasons=decision["reasons"], facts=facts, line=line,
                          qty_received=qty_received, lot=lot, expiry=expiry,
                          thresholds=thresholds, today=today, photo_refs=photo_refs)
    verdict = rollup(checks)
    explain_lines = E.explain(
        decision["reasons"], facts=facts, line=line, qty_received=qty_received,
        lot=lot, expiry=expiry, thresholds=thresholds, today=today,
        photo_count=facts.get("photo_count", 0))

    wf = workflow_id_for(org_id, subject_id)
    request_stub = {"workflow_id": wf, "stage": "receiving",
                    "subject": {"org_id": org_id, "subject_id": subject_id},
                    "previous_evidence": previous_evidence or []}

    damage_fact = facts["damage"]
    if damage_fact.get("source") == "vlm":
        cfg = config.vlm_config()
        model = {"name": damage_fact.get("model") or cfg.get("model") or "vlm",
                 "version": "1", "provider": cfg.get("provider"),
                 "prompt_version": damage_fact.get("prompt_version"),
                 "calls": 1, "cost_usd": None}
    else:
        model = {"name": "receiving-rules", "version": config.RULES_VERSION,
                 "provider": None, "prompt_version": None, "calls": 0, "cost_usd": None}

    expected_qty = line.get("qty_expected")
    payload = {
        "rcv_id": rcv_id, "attempt": attempt, "scan_key": scan_key, "source": source,
        "po_id": line.get("po_id"), "po_line": line.get("line_no"),
        "gtin": line.get("gtin") or None, "supplier": line.get("supplier") or None,
        "sku": line.get("sku") or None, "asin": line.get("asin") or None,
        "description": line.get("description") or None,
        "qty_expected": expected_qty, "qty_received": qty_received,
        "shortfall_units": (max(int(expected_qty) - int(qty_received), 0)
                            if (expected_qty is not None and qty_received is not None) else None),
        "lot_entered": lot or None, "expiry_entered": expiry or None,
        "operator": operator, "rules_version": config.RULES_VERSION,
        "thresholds": thresholds,
        "reasons": decision["reasons"], "plan_verdict": state,
        "facts": facts, "quality_flags": [f for f in decision["reasons"] if f.startswith("IMG_")],
        "photos": [{"role": p.get("role"), "ref": p.get("ref"), "sha256": p.get("sha256"),
                    "quality": next((q for q in facts["quality"] if q.get("role") == p.get("role")), None)}
                   for p in photos],
        "explain": explain_lines,
        "retake": {"offered": offer, "attempt": attempt, "coach": coach_obj},
    }

    record_id = record_id_for(request_id)
    signature = None

    def build(rid: str) -> dict:
        return build_record(
            request_stub, agent_id=config.AGENT_ID, record_id=rid,
            captured_at=utcnow(), checks=checks, outcome=outcome,
            reason="; ".join(ln["text"] for ln in explain_lines) or "all checks passed",
            model=model, unit_scope="po_line",
            refs={"po_number": line.get("po_id"), "po_line": line.get("line_no"),
                  "sku": line.get("sku"), "asin": line.get("asin"),
                  "gtin": line.get("gtin"), "rcv_id": rcv_id},
            operator_id=operator,
            inputs=[{"ref": p["ref"], "sha256": p.get("sha256"), "kind": "image"} for p in photos],
            payload=payload, status="pending" if offer else "completed",
            verdict=verdict,
            confidence=round(float(damage_fact.get("conf")), 4)
                      if damage_fact.get("source") == "vlm" else None,
            needs_human=state in (D.QUARANTINE, D.ESCALATE),
            latency_ms=int((time.perf_counter() - started) * 1000))

    existing = db.get_record(record_id)
    if existing is not None:
        signature = _findings_signature(existing, FINDINGS_KEYS)
        probe = build(record_id)
        if _findings_signature(probe, FINDINGS_KEYS) == signature:
            return build_output(existing, next_step=_state_view(
                existing["payload"].get("plan_verdict", D.QUARANTINE))[1],
                reason=existing["decision"]["reason"])
        # different findings for the same request: contract says a new record_id
        record_id = f"{record_id}-{_findings_signature(probe, FINDINGS_KEYS)[:8]}"

    record = build(record_id)
    db.save_record(record)

    # session bookkeeping (UI flows create the row before evaluate; orchestrator does not)
    if rcv_id:
        session = db.get_receiving(rcv_id)
        if session is not None:
            fields = {"attempt": attempt, "verdict": state, "reasons": json.dumps(decision["reasons"]),
                      "facts": json.dumps(facts, sort_keys=True), "effective_record_id": record_id,
                      "qty_received": qty_received}
            if offer:
                fields["status"] = "pending_retake"
            elif state in (D.QUARANTINE, D.ESCALATE):
                fields["status"] = "final_open"
            else:
                fields["status"] = "final_closed"
            db.update_receiving(rcv_id, **fields)
            if not offer:
                db.append_event(RECEIVING_FINAL, rcv_id, record_id, _event_payload(
                    record, state=state, rcv_id=rcv_id))

    return build_output(record, next_step=next_step, reason=record["decision"]["reason"])


def _event_payload(record: dict, *, state: str, rcv_id: str) -> dict:
    p = record["payload"]
    return {
        "rcv_id": rcv_id, "record_id": record["record_id"],
        "workflow_id": record["workflow_id"], "subject": dict(record["subject"]),
        "effective_verdict": state, "verdict": record["decision"]["verdict"],
        "outcome": record["decision"]["outcome"], "reasons": p.get("reasons", []),
        "manifest_line": {"po_id": p.get("po_id"), "line_no": p.get("po_line"),
                          "gtin": p.get("gtin")},
        "qty_received": p.get("qty_received"),
        "image_sha256": [i.get("sha256") for i in record.get("inputs", []) if i.get("sha256")],
        "ts": record["produced_at"],
    }


# --------------------------------------------------------------------------------------
# orchestrator entry (Agent Input -> Agent Output)
# --------------------------------------------------------------------------------------

def evaluate_agent_input(request: dict) -> dict:
    org = request["subject"]["org_id"]
    subject = request["subject"]["subject_id"]
    line = db.find_manifest_line(org, subject)
    if line is None:  # unknown subject OR another tenant's subject -> refuse, never answer
        raise LookupError(f"no receiving record for {subject} in {org}")

    photos = []
    for item in request.get("inputs") or []:
        if item.get("kind") not in (None, "image"):
            continue
        ref = item.get("ref")
        path = config.INPUT_DIR / ref
        photos.append({"role": _role_from_ref(ref), "ref": ref,
                       "sha256": item.get("sha256") or _sha256_file(path), "path": str(path)})

    request_id = request.get("request_id") or f"{workflow_id_for(org, subject)}:receiving"
    scan_key = "req:" + hashlib.sha256(request_id.encode()).hexdigest()[:16]
    session = db.get_receiving_by_scan_key(scan_key)

    if session is None:
        with _SESSION_LOCK, db.connect() as conn:
            proposed = db.next_rcv_id(conn)
        db.create_receiving(
            rcv_id=proposed, scan_key=scan_key,
            workflow_id=workflow_id_for(org, subject), org_id=org, subject_id=subject,
            manifest_line_id=line["id"], qty_received=None, lot_entered="", expiry_entered="",
            status="final_open", operator=None)
        session = db.get_receiving_by_scan_key(scan_key)
        for p in photos:
            db.add_photo(session["id"], role=p["role"], attempt=0, sha256=p["sha256"] or "",
                         path=p["path"], quality={}, barcode={})
    rcv_id = session["rcv_id"]

    return evaluate(
        request_id=request_id, org_id=org, subject_id=subject, line=line,
        qty_received=None, lot="", expiry="", photos=photos, operator=None,
        previous_evidence=request.get("previous_evidence"), attempt=0,
        rcv_id=rcv_id, scan_key=scan_key, allow_retake=False, source="orchestrator")


def _role_from_ref(ref: str | None) -> str:
    name = (ref or "").rsplit("/", 1)[-1].lower()
    for role in ROLES:
        if role in name:
            return role
    return "overall"


def _sha256_file(path) -> str | None:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


# --------------------------------------------------------------------------------------
# UI flows (scan -> retake/skip -> override)
# --------------------------------------------------------------------------------------

def _store_uploads(rcv_id: str, attempt: int, uploads: list[tuple[str, bytes]]) -> list[dict]:
    """Persist uploaded photos under the media dir, resized to <=1600px, hashed."""
    from PIL import Image

    out = []
    folder = config.MEDIA_DIR / rcv_id
    folder.mkdir(parents=True, exist_ok=True)
    for index, (role, data) in enumerate(uploads):
        if role not in ROLES:
            raise ValueError(f"unknown photo role: {role}")
        try:
            img = Image.open(io.BytesIO(data))
            if max(img.size) > 1600:
                img.thumbnail((1600, 1600))
            buffer = io.BytesIO()
            img.convert("RGB").save(buffer, format="JPEG", quality=88)
            data = buffer.getvalue()
            suffix = "jpg"
        except Exception as exc:
            raise ValueError(f"unreadable {role} photo: {exc}") from exc
        sha = hashlib.sha256(data).hexdigest()
        path = folder / f"a{attempt}_{role}_{index}.{suffix}"
        path.write_bytes(data)
        out.append({"role": role, "ref": f"{rcv_id}/{path.name}", "sha256": sha,
                    "path": str(path)})
    return out


def _session(rcv_id: str) -> dict:
    row = db.get_receiving(rcv_id)
    if row is None:
        raise LookupError(f"no receiving {rcv_id}")
    return row


def _photos_from_session(session: dict, attempt: int) -> list[dict]:
    return [{"role": p["role"], "ref": p["path"], "sha256": p["sha256"], "path": p["path"]}
            for p in db.photos_for(session["id"], attempt)]


def start_scan(*, org_id: str, line_id: int, qty_received: int | None, lot: str,
               expiry: str, operator: str | None, uploads: list[tuple[str, bytes]]) -> dict:
    line = db.get_manifest_line(org_id, line_id)
    if line is None:  # wrong tenant or unknown line -> refuse
        raise LookupError(f"no manifest line {line_id} in {org_id}")
    if not any(role == "label" for role, _ in uploads):
        raise ValueError("a 'label' photo is required")
    if qty_received is None:
        raise ValueError("qty_received is required")

    subject = line["unit_id"] or f"{line['po_id']}-L{line['line_no']}"
    scan_key = uuid.uuid4().hex
    with _SESSION_LOCK, db.connect() as conn:
        proposed = db.next_rcv_id(conn)
    db.create_receiving(
        rcv_id=proposed, scan_key=scan_key, workflow_id=workflow_id_for(org_id, subject),
        org_id=org_id, subject_id=subject, manifest_line_id=line["id"],
        qty_received=qty_received, lot_entered=lot or "", expiry_entered=expiry or "",
        status="pending_retake", operator=operator)
    session = db.get_receiving_by_scan_key(scan_key)
    photos = _store_uploads(proposed, 0, uploads)
    for p in photos:
        db.add_photo(session["id"], role=p["role"], attempt=0, sha256=p["sha256"],
                     path=p["path"], quality={}, barcode={})

    out = evaluate(
        request_id=f"{session['workflow_id']}:receiving:scan:{scan_key}",
        org_id=org_id, subject_id=subject, line=line, qty_received=qty_received,
        lot=lot or "", expiry=expiry or "", photos=photos, operator=operator,
        attempt=0, rcv_id=proposed, scan_key=scan_key, allow_retake=True, source="ui")
    return ui_response(out)


def do_retake(rcv_id: str, uploads: list[tuple[str, bytes]], operator: str | None = None) -> dict:
    session = _session(rcv_id)
    if session["status"] != "pending_retake":
        raise ValueError(f"retake not allowed in status {session['status']}")
    attempt = session["attempt"] + 1
    if not uploads:
        raise ValueError("retake needs at least one photo")
    photos = _store_uploads(rcv_id, attempt, uploads)
    for p in photos:
        db.add_photo(session["id"], role=p["role"], attempt=attempt, sha256=p["sha256"],
                     path=p["path"], quality={}, barcode={})
    line = db.get_manifest_line(session["org_id"], session["manifest_line_id"]) if session["manifest_line_id"] else None
    out = evaluate(
        request_id=f"{session['workflow_id']}:receiving:scan:{session['scan_key']}:retake{attempt}",
        org_id=session["org_id"], subject_id=session["subject_id"], line=line,
        qty_received=session["qty_received"], lot=session["lot_entered"],
        expiry=session["expiry_entered"], photos=photos,
        operator=session["operator"], attempt=attempt, rcv_id=rcv_id,
        scan_key=session["scan_key"], allow_retake=False, source="ui")  # always finalizes
    return ui_response(out)


def do_finalize(rcv_id: str) -> dict:
    """'Skip retake': finalize with the evidence already captured. No re-capture, no prompt."""
    session = _session(rcv_id)
    if session["status"] != "pending_retake":
        raise ValueError(f"finalize not allowed in status {session['status']}")
    attempt = session["attempt"]
    photos = _photos_from_session(session, attempt)
    line = db.get_manifest_line(session["org_id"], session["manifest_line_id"]) if session["manifest_line_id"] else None
    out = evaluate(
        request_id=f"{session['workflow_id']}:receiving:scan:{session['scan_key']}:finalize{attempt}",
        org_id=session["org_id"], subject_id=session["subject_id"], line=line,
        qty_received=session["qty_received"], lot=session["lot_entered"],
        expiry=session["expiry_entered"], photos=photos,
        operator=session["operator"], attempt=attempt, rcv_id=rcv_id,
        scan_key=session["scan_key"], allow_retake=False, source="ui")
    return ui_response(out)


def do_override(rcv_id: str, *, final_verdict: str, reason_code: str, note: str,
                operator: str) -> dict:
    """Append-only override: original checks/decision are never rewritten."""
    if final_verdict not in (D.ACCEPT, D.REJECT):
        raise ValueError("final_verdict must be ACCEPT or REJECT")
    if reason_code not in OVERRIDE_REASONS:
        raise ValueError(f"reason_code must be one of {', '.join(OVERRIDE_REASONS)}")
    if reason_code == "OTHER" and not (note or "").strip():
        raise ValueError("a note is required for reason_code OTHER")
    if not (operator or "").strip():
        raise ValueError("operator is required")

    session = _session(rcv_id)
    if session["status"] == "pending_retake":
        # the record on this session is a retake offer, not a judgment: retake or skip first
        raise ValueError("finish the retake (or skip it) before overriding")
    record_id = session.get("effective_record_id")
    record = db.get_record(record_id) if record_id else None
    if record is None:
        raise LookupError(f"no finalized record for {rcv_id}")

    contract_verdict = "PASS" if final_verdict == D.ACCEPT else "FAIL"
    reason_text = reason_code + (f": {note.strip()}" if (note or "").strip() else "")
    updated = add_agent_override(record, by=operator.strip(), target="decision",
                                 new_verdict=contract_verdict, reason=reason_text)
    stored = db.append_override(record_id, updated["overrides"][-1])

    db.update_receiving(rcv_id, status="final_closed", verdict=final_verdict)
    db.append_event(RECEIVING_OVERRIDDEN, rcv_id, record_id, {
        "rcv_id": rcv_id, "record_id": record_id,
        "workflow_id": stored["workflow_id"], "subject": dict(stored["subject"]),
        "original_verdict": stored["payload"].get("plan_verdict"),
        "effective_verdict": final_verdict,
        "contract_verdict": contract_verdict,
        "reason_code": reason_code, "note": (note or "").strip(),
        "operator": operator.strip(), "ts": utcnow(),
    })
    return ui_response(build_output(stored))


def ui_response(out: dict) -> dict:
    """Agent Output -> the plan section 7 response the UI renders."""
    record = out["evidence"]
    payload = record["payload"]
    rcv_id = payload.get("rcv_id")
    session = db.get_receiving(rcv_id) if rcv_id else None
    effective = session["verdict"] if session else payload.get("plan_verdict")
    return {
        "rcv_id": rcv_id,
        "status": session["status"] if session else ("pending" if record["status"] == "pending" else "final_closed"),
        "attempt": payload.get("attempt", 0),
        "verdict": payload.get("plan_verdict"),
        "effective_verdict": effective,
        "original_verdict": payload.get("plan_verdict"),
        "reasons": payload.get("reasons", []),
        "explain": payload.get("explain", []),
        "retake_offered": payload.get("retake", {}).get("offered", False),
        "coach": payload.get("retake", {}).get("coach"),
        "facts": payload.get("facts", {}),
        "manifest_line": {"po_id": payload.get("po_id"), "line_no": payload.get("po_line"),
                          "gtin": payload.get("gtin"), "qty_expected": payload.get("qty_expected")},
        "qty_received": payload.get("qty_received"),
        "override": (record.get("overrides") or [None])[-1],
        "record": record,
        "next_step": out["next_step_recommendation"],
    }
