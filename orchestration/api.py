"""HTTP front door for the orchestrator and live operations cockpit.

  uvicorn orchestration.api:app --port 8100 --host 0.0.0.0
  GET  /                          -> Linear-style Desktop Cockpit
  GET  /scanner                   -> Handheld Mobile Phone Scanner
  GET  /api/lan-ip                -> Discovers local LAN IP for QR pairing
  GET  /api/scanner-qr            -> PNG QR code for smartphone camera
  POST /api/capture               -> Ingests photo from phone, runs pipeline, broadcasts SSE
  POST /api/simulate-capture      -> Offline fallback synthetic capture generator
  GET  /api/events                -> Server-Sent Events (SSE) stream for live updates
  POST /workflows                 {"org_id": "...", "unit_id": "..."} -> Runs workflow
  GET  /workflows/{id}            -> Workflow state
  GET  /workflows/{id}/evidence   -> Evidence bundle
  POST /workflows/{id}/resume     -> Continue after a halt
  POST /workflows/{id}/overrides  -> Human override
  GET  /health                    -> Health check
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import socket
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import qrcode
from PIL import Image, ImageDraw

from shared.utils import sample_data

from .clients import HttpClient, client_for, load_manifest
from .orchestrator import (
    advance,
    apply_override,
    bundle,
    default_flow_path,
    flow_stages,
    load_flow,
    new_workflow,
    resume,
    run_workflow,
    workflow_id_for,
)
from .store import EvidenceConflict, FileStore

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="CUBE Round 3 Orchestrator & Commerce Cockpit")
FLOW = os.environ.get("ORCH_FLOW") or default_flow_path()
STORE = FileStore()

# In-memory Server-Sent Events subscriber queues
SUBSCRIBERS: list[asyncio.Queue] = []


@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def get_lan_ip() -> str:
    """Detects local LAN IP for seamless phone pairing over local Wi-Fi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def broadcast_event(event: str, data: dict) -> None:
    """Broadcasts a real-time event to all connected cockpit browsers."""
    msg = f"data: {json.dumps({'event': event, 'data': data})}\n\n"
    dead = []
    for q in SUBSCRIBERS:
        try:
            await q.put(msg)
        except Exception:
            dead.append(q)
    for q in dead:
        if q in SUBSCRIBERS:
            SUBSCRIBERS.remove(q)


@app.get("/health")
def health() -> dict:
    agents = {}
    for stage in flow_stages(load_flow(FLOW)):
        client = client_for(stage)
        try:
            agents[stage] = client.health() if isinstance(client, HttpClient) else {"status": "ok", "mode": "inproc"}
        except Exception as exc:
            agents[stage] = {"status": "down", "error": str(exc)[:200], "owner": load_manifest(stage)["owner"]}
    ok = all(a["status"] == "ok" for a in agents.values())
    return {"status": "ok" if ok else "degraded", "flow": load_flow(FLOW)["flow_id"], "agents": agents}


@app.get("/api/lan-ip")
def lan_ip() -> dict:
    ip = get_lan_ip()
    port = int(os.environ.get("PORT", 8100))
    return {"ip": ip, "port": port, "scanner_url": f"http://{ip}:{port}/scanner"}


@app.get("/api/scanner-qr")
def scanner_qr() -> Response:
    ip = get_lan_ip()
    port = int(os.environ.get("PORT", 8100))
    url = f"http://{ip}:{port}/scanner"
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.get("/api/events")
async def sse_events() -> StreamingResponse:
    q = asyncio.Queue()
    SUBSCRIBERS.append(q)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                msg = await q.get()
                yield msg
        except asyncio.CancelledError:
            if q in SUBSCRIBERS:
                SUBSCRIBERS.remove(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/capture")
async def capture(
    file: UploadFile = File(...),
    unit_id: str = Form("UNIT-0014"),
    stage: str = Form("receiving"),
    org_id: str = Form("org_demo_alpha"),
) -> dict:
    """Ingests capture from connected handheld phone, routes to agent, executes tasks, and broadcasts real-time results."""
    content = await file.read()
    sha256 = hashlib.sha256(content).hexdigest()
    target_dir = ROOT / "data" / "input" / unit_id / stage
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "capture.jpg").write_bytes(content)

    img_url = f"/api/image/{unit_id}/{stage}/capture.jpg"

    # Step 1: Broadcast immediate delivery confirmation & set frontend output panels to LOADING state
    await broadcast_event("capture", {
        "unit_id": unit_id,
        "stage": stage,
        "org_id": org_id,
        "sha256": sha256,
        "size_bytes": len(content),
        "url": img_url,
        "status": "processing",
        "delivery_confirmed": True,
        "message": f"Orchestrator confirmed delivery. Routing image data to {stage} agent for real-time inspection...",
    })

    # Yield control to event loop so SSE message flushes to cockpit browser immediately
    await asyncio.sleep(0.05)

    case = {
        "org_id": org_id,
        "unit_id": unit_id,
        "route": "all",
        "returned": True,
    }
    wf = STORE.load_workflow(workflow_id_for(case))
    if wf is None:
        wf = new_workflow(case, load_flow(FLOW))

    # Reset state of target stage so orchestrator routes fresh capture to agent
    for sr in wf["stage_results"]:
        if sr["stage"] == stage:
            sr["state"] = "pending"
            sr["attempts"] = 0
            sr["error"] = None

    # If prep or returns changed, recovery should also re-audit
    if stage in ("prep", "returns"):
        for sr in wf["stage_results"]:
            if sr["stage"] == "recovery":
                sr["state"] = "pending"
                sr["attempts"] = 0
                sr["error"] = None

    # Step 2: Route image data to agent and execute required tasks
    wf = await asyncio.to_thread(advance, wf, load_flow(FLOW), STORE)
    ev_bundle = bundle(wf, STORE)

    # Step 3: Broadcast completion event with full evidence for frontend display
    await broadcast_event("workflow", {
        "workflow": wf,
        "evidence": ev_bundle["evidence"],
        "stage": stage,
        "status": "completed",
    })

    # Step 4: Return confirmed delivery & results to phone
    return {
        "status": "delivered",
        "delivery_confirmed": True,
        "orchestrator_routed_to": stage,
        "sha256": sha256,
        "unit_id": unit_id,
        "stage": stage,
        "url": img_url,
        "workflow": wf,
        "evidence": ev_bundle["evidence"],
    }


@app.get("/api/image/{unit_id}/{stage}/{filename}")
def get_image(unit_id: str, stage: str, filename: str) -> FileResponse:
    p = ROOT / "data" / "input" / unit_id / stage / filename
    if p.exists():
        return FileResponse(p)
    for fix_folder in [ROOT / "data" / "fixtures" / stage, ROOT / "fixtures" / stage, ROOT / "data" / "sample"]:
        cand = fix_folder / filename
        if cand.exists():
            return FileResponse(cand)
    raise HTTPException(404, "Image not found")


@app.get("/api/ref/{path:path}")
def get_ref(path: str) -> FileResponse:
    candidates = [
        ROOT / "data" / "input" / path,
        ROOT / "data" / path,
        ROOT / path,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return FileResponse(c)
    raise HTTPException(404, f"Ref not found: {path}")


@app.get("/api/active-workflow")
def active_workflow(unit_id: str = "UNIT-0014", org_id: str = "org_demo_alpha") -> dict:
    case = {
        "org_id": org_id,
        "unit_id": unit_id,
        "route": "all",
        "returned": True,
    }
    wf = STORE.load_workflow(workflow_id_for(case))
    if wf is None:
        wf = run_workflow(case, load_flow(FLOW), STORE)
    ev_bundle = bundle(wf, STORE)
    return {
        "workflow": wf,
        "evidence": ev_bundle["evidence"],
        "workflows": STORE.list_workflows(),
    }


@app.get("/api/workflows")
def list_workflows_endpoint() -> dict:
    return {"workflows": STORE.list_workflows()}


@app.post("/workflows")
async def create_workflow_endpoint(body: dict) -> dict:
    org, subject = body.get("org_id"), body.get("subject_id") or body.get("unit_id")
    if not org or not subject:
        raise HTTPException(422, "org_id and unit_id (or subject_id) are required")
    case = {
        "org_id": org,
        "unit_id": subject,
        "route": body.get("route") or sample_data.route(subject, org),
        "returned": body.get("returned", sample_data.has("returns", subject, org)),
    }
    wf = run_workflow(case, load_flow(FLOW), STORE)
    await broadcast_event("workflow", wf)
    return wf


def _get(workflow_id: str) -> dict:
    wf = STORE.load_workflow(workflow_id)
    if wf is None:
        raise HTTPException(404, f"no workflow {workflow_id}")
    return wf


@app.get("/workflows/{workflow_id}")
def get_workflow_endpoint(workflow_id: str) -> dict:
    return _get(workflow_id)


@app.get("/workflows/{workflow_id}/evidence")
def evidence(workflow_id: str) -> dict:
    return bundle(_get(workflow_id), STORE)


@app.post("/workflows/{workflow_id}/resume")
async def resume_workflow(workflow_id: str) -> dict:
    _get(workflow_id)
    wf = resume(workflow_id, load_flow(FLOW), STORE)
    await broadcast_event("workflow", wf)
    return wf


@app.post("/workflows/{workflow_id}/overrides")
async def override(workflow_id: str, body: dict) -> dict:
    _get(workflow_id)
    try:
        wf = apply_override(
            workflow_id,
            STORE,
            record_id=body.get("record_id", ""),
            new_verdict=body.get("new_verdict", ""),
            actor=body.get("actor", ""),
            reason=body.get("reason", ""),
            new_outcome=body.get("new_outcome"),
        )
        await broadcast_event("workflow", wf)
        return wf
    except (ValueError, EvidenceConflict) as exc:
        raise HTTPException(422, str(exc)) from exc


# Mount Static Files & Page Routes
STATIC_DIR = ROOT / "orchestration" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index_page():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    @app.get("/landing", include_in_schema=False)
    def landing_page():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    @app.get("/cockpit", include_in_schema=False)
    def cockpit_page():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    @app.get("/scanner", include_in_schema=False)
    def scanner_page():
        return FileResponse(STATIC_DIR / "scanner.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

