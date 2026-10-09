"""Receiving Manager v2: agent entry point + the one app (decision: single app on make_app).

- `handle(agent_input) -> agent_output` is what the orchestrator calls (in-process or POST /run).
- The same FastAPI app serves the scan UI, the review-queue API, and the events feed.
  `mode` stays `inproc` because tests/conftest.py forces ORCH_MODE=inproc; the HTTP
  contract endpoints exist for non-Python-style consumers and for `make run --http`.

Fail-open rules (plan / contract rule 3):
- model errors are handled inside damage.assess -> fail-safe facts, never an exception
- any unexpected error inside handle() returns pending_output (never raises to the caller)
- LookupError (unknown subject / wrong tenant) IS raised: refuse, never answer.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, db, service
from .service import (do_finalize, do_override, do_retake,
                      evaluate_agent_input, start_scan)
from shared.utils.records import pending_output

STAGE = config.STAGE
AGENT_ID = config.AGENT_ID


def handle(request: dict) -> dict:
    """Agent Input -> Agent Output. Contract entry point (in-process and POST /run)."""
    if request.get("stage") and request.get("stage") != STAGE:
        raise LookupError(f"stage must be '{STAGE}'")
    try:
        return evaluate_agent_input(request)
    except LookupError:
        raise  # tenancy / unknown subject: the server maps this to 404
    except Exception as exc:  # fail open: an agent bug must still produce an output
        return pending_output(request, code="agent_exception",
                              message=f"{type(exc).__name__}: {exc}", agent_id=AGENT_ID)


def build_app() -> FastAPI:
    db.init_db()
    from shared.utils.server import make_app
    app = make_app(STAGE, handle)

    static_dir = Path(__file__).with_name("static")
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    media_dir = config.MEDIA_DIR
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

    @app.get("/", include_in_schema=False)
    def index():
        page = static_dir / "index.html"
        if page.exists():
            return FileResponse(str(page))
        return JSONResponse({"stage": STAGE, "hint": "/docs, /api/manifest, /health"})

    # ---- manifest ------------------------------------------------------------------
    @app.get("/api/manifest")
    def get_manifest(org: str | None = None):
        return db.list_manifest(org)

    @app.post("/api/manifest")
    def post_manifest(file: UploadFile = File(...), org: str = Form("org_demo_alpha")):
        try:
            text = file.file.read().decode("utf-8-sig")
            rows = db.parse_manifest_csv(text, org)
            with db.connect() as conn:
                written = db.import_manifest_rows(conn, rows, org)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"imported": written, "org": org}

    # ---- receivings ----------------------------------------------------------------
    def _uploads(files: list[UploadFile] | None, roles: str | None) -> list[tuple[str, bytes]]:
        role_list = [r.strip() for r in (roles or "").split(",") if r.strip()]
        out = []
        for i, f in enumerate(files or []):
            role = role_list[i] if i < len(role_list) else (f.filename or "")
            if role not in service.ROLES:
                # fall back to a role guessed from the filename, else overall
                role = service._role_from_ref(f.filename)
            out.append((role, f.file.read()))
        return out

    def _form_int(value: str | None) -> int | None:
        if value is None or str(value).strip() == "":
            return None
        return int(value)

    @app.post("/api/receivings")
    def create_receiving(files: list[UploadFile] = File(None), roles: str = Form(None),
                         org_id: str = Form(...), line_id: int = Form(...),
                         qty_received: str = Form(...), lot: str = Form(""),
                         expiry: str = Form(""), operator: str = Form("")):
        try:
            uploads = _uploads(files, roles)
            return start_scan(org_id=org_id, line_id=line_id,
                              qty_received=_form_int(qty_received), lot=lot, expiry=expiry,
                              operator=operator or None, uploads=uploads)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.post("/api/receivings/{rcv_id}/retake")
    def retake(rcv_id: str, files: list[UploadFile] = File(None), roles: str = Form(None),
               operator: str = Form("")):
        try:
            return do_retake(rcv_id, _uploads(files, roles), operator or None)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.post("/api/receivings/{rcv_id}/finalize")
    def finalize(rcv_id: str):
        try:
            return do_finalize(rcv_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.post("/api/receivings/{rcv_id}/override")
    async def override(rcv_id: str, body: dict):
        try:
            return do_override(rcv_id, final_verdict=body.get("final_verdict", ""),
                               reason_code=body.get("reason_code", ""),
                               note=body.get("note", ""), operator=body.get("operator", ""))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.get("/api/receivings")
    def list_receivings(status: str | None = None, verdict: str | None = None,
                        org: str | None = None, source: str | None = None):
        rows = db.list_receivings(status=status, verdict=verdict, org_id=org, source=source)
        out = []
        for row in rows:
            record = db.get_record(row["effective_record_id"]) if row.get("effective_record_id") else None
            payload = (record or {}).get("payload", {})
            photos = db.photos_for(row["id"])
            out.append({
                "rcv_id": row["rcv_id"], "status": row["status"], "attempt": row["attempt"],
                "org_id": row["org_id"], "subject_id": row["subject_id"],
                "workflow_id": row["workflow_id"],
                "verdict": payload.get("plan_verdict") or row["verdict"],
                "effective_verdict": row["verdict"],
                "reasons": json.loads(row["reasons"] or "[]"),
                "created_at": row["created_at"], "operator": row["operator"],
                "record_id": row.get("effective_record_id"),
                "photos": [{"role": p["role"], "sha256": p["sha256"],
                            "url": f"/media/{row['rcv_id']}/{Path(p['path']).name}"}
                           for p in photos[-3:]],
            })
        return out

    @app.get("/api/receivings/{rcv_id}")
    def get_receiving(rcv_id: str):
        row = db.get_receiving(rcv_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"no receiving {rcv_id}")
        record = db.get_record(row["effective_record_id"]) if row.get("effective_record_id") else None
        if record is None:
            raise HTTPException(status_code=404, detail=f"no record for {rcv_id}")
        payload = record.get("payload", {})
        return {
            "rcv_id": rcv_id, "status": row["status"], "attempt": row["attempt"],
            "manifest_line": {"po_id": payload.get("po_id"), "line_no": payload.get("po_line"),
                              "gtin": payload.get("gtin"),
                              "qty_expected": payload.get("qty_expected")},
            "qty_received": payload.get("qty_received"),
            "verdict": payload.get("plan_verdict"),
            "effective_verdict": row["verdict"],
            "reasons": payload.get("reasons", []),
            "override": (record.get("overrides") or [None])[-1],
            "attempt_history": len(db.records_for(rcv_id)),
            "facts": payload.get("facts", {}),
            "images": [{"role": p.get("role"), "sha256": p.get("sha256"),
                        "quality": p.get("quality")} for p in payload.get("photos", [])],
            "rules_version": payload.get("rules_version"),
            "ts": record.get("produced_at"),
            "record": record,   # the full sealed Evidence Record
        }

    # ---- events feed (W7 handoff) ---------------------------------------------------
    @app.get("/api/events")
    def events(since: int = 0):
        return db.list_events(since)

    @app.get("/api/healthz")
    def healthz():
        return {"status": "ok", "stage": STAGE, "db": str(config.DB_PATH)}

    return app


app = build_app()
