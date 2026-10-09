"""Inspection pipeline orchestration (v2).

Per uploaded photo: image validation (caller) -> OCR -> YOLO -> Groq/Qwen
visual reasoning -> per-photo structured evidence -> RETURN-LEVEL aggregated
deterministic decision (all photos of the return) -> persistence + audit.

Runs synchronously (RapidOCR ≈ 0.5-2 s, yolov8n ≈ 50-300 ms on CPU, Groq vision
≈ 1-5 s) — acceptable for one photo per request without a job queue; the
stages persist individually so a worker can be introduced later.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.returns.backend.app.models import (
    AIAnalysis,
    AuditAction,
    Decision,
    Detection,
    DetectionRun,
    EvidenceRecord,
    Inspection,
    OCRResult,
    ReturnStatus,
    User,
)
from agents.returns.backend.app.services import decision_service, evidence_service, groq_service, ocr_service, yolo_service
from agents.returns.backend.app.services.audit_service import record_event
from agents.returns.backend.app.services.image_service import StoredImage

logger = logging.getLogger("returnguard.inspection")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_inspection(
    db: Session,
    *,
    return_record,
    agent: User,
    stored: StoredImage,
    otp_challenge_id: str | None,
    view_type: str = "STANDARD",
    actor_ip: str | None = None,
) -> Inspection:
    """Persist the upload and run the full evidence pipeline."""
    if view_type not in ("STANDARD", "CONTENTS_LAYOUT"):
        view_type = "STANDARD"

    inspection = Inspection(
        return_id=return_record.id,
        agent_id=agent.id,
        otp_challenge_id=otp_challenge_id,
        status="PROCESSING",
        image_stored_name=stored.stored_name,
        image_original_name=stored.original_name,
        image_content_type=stored.content_type,
        image_size_bytes=stored.size_bytes,
        image_sha256=stored.sha256,
        image_width=stored.width,
        image_height=stored.height,
        view_type=view_type,
    )
    db.add(inspection)
    db.flush()

    ocr_data = _safe_run(ocr_service.run_ocr, stored.path, "OCR",
                         ocr_service.OCRData(engine="unknown", engine_version="", status="FAILED"))
    det_data = _safe_run(yolo_service.run_detection, stored.path, "YOLO",
                         yolo_service.DetectionData(status="FAILED"))

    # --- Groq/Qwen visual reasoning over the photos collected so far (max 3) ---
    siblings = db.scalars(
        select(Inspection)
        .where(Inspection.return_id == return_record.id, Inspection.status == "COMPLETED")
        .order_by(Inspection.created_at.asc())
    ).all()
    prior_paths = []
    for sib in siblings:
        try:
            from agents.returns.backend.app.services.image_service import resolve_stored_path

            prior_paths.append(resolve_stored_path(sib.return_id, sib.image_stored_name))
        except Exception:  # pragma: no cover - missing file on disk
            continue
    ai_data = groq_service.run_ai_analysis(
        return_record,
        image_paths=[stored.path, *prior_paths][: groq_service.MAX_IMAGES_PER_REQUEST],
        ocr_texts=[ocr_data.full_text],
        detections=[
            {"label": d.class_label, "confidence": d.confidence, "bbox": d.bbox} for d in det_data.detections
        ],
        view_types=[view_type] + [s.view_type for s in siblings],
    )

    ocr_row = OCRResult(
        inspection_id=inspection.id,
        engine=ocr_data.engine,
        engine_version=ocr_data.engine_version,
        status=ocr_data.status,
        full_text=ocr_data.full_text,
        mean_confidence=ocr_data.mean_confidence,
        blocks=[{"text": b.text, "confidence": b.confidence, "box": b.box} for b in ocr_data.blocks],
        processing_ms=ocr_data.processing_ms,
        error=ocr_data.error,
    )
    db.add(ocr_row)

    run_row = DetectionRun(
        inspection_id=inspection.id,
        model_name=det_data.model_name,
        model_path=det_data.model_path,
        device=det_data.device,
        confidence_threshold=det_data.confidence_threshold,
        status=det_data.status,
        inference_ms=det_data.inference_ms,
        error=det_data.error,
    )
    db.add(run_row)
    db.flush()
    for det in det_data.detections:
        db.add(Detection(run_id=run_row.id, class_id=det.class_id, class_label=det.class_label,
                         confidence=det.confidence, bbox=det.bbox))
    db.flush()

    db.add(AIAnalysis(
        inspection_id=inspection.id,
        provider=ai_data.provider,
        model=ai_data.model,
        status=ai_data.status,
        latency_ms=ai_data.latency_ms,
        attempts=ai_data.attempts,
        payload=ai_data.payload,
        error=ai_data.error,
    ))

    evidence_payload = evidence_service.build_evidence(return_record, ocr_data, det_data, ai_data, view_type)
    db.add(EvidenceRecord(inspection_id=inspection.id, payload=evidence_payload))
    inspection.status = "COMPLETED"
    inspection.completed_at = _utcnow()

    # --- return-level aggregated decision over ALL completed inspections ---
    all_inspections = db.scalars(
        select(Inspection)
        .where(Inspection.return_id == return_record.id, Inspection.status == "COMPLETED")
        .order_by(Inspection.created_at.asc())
    ).all()
    payloads = [
        i.evidence.payload for i in all_inspections if i.evidence is not None and i.id != inspection.id
    ] + [evidence_payload]

    result = decision_service.decide(payloads)
    db.add(Decision(
        inspection_id=inspection.id,
        return_id=return_record.id,
        outcome=result.outcome,
        disposition=result.disposition,
        rationale=result.rationale,
        engine_version=decision_service.ENGINE_VERSION,
    ))

    if result.outcome == "MANUAL_REVIEW":
        return_record.status = ReturnStatus.NEEDS_REVIEW
    elif result.outcome == "APPROVE":
        return_record.status = ReturnStatus.APPROVED
    else:
        return_record.status = ReturnStatus.REJECTED

    record_event(
        db, action=AuditAction.INSPECTION_CREATED, entity_type="inspection", entity_id=inspection.id,
        actor_id=agent.id, actor_role=agent.role,
        details={"return_code": return_record.return_code, "view_type": view_type,
                 "ocr_status": ocr_data.status, "detection_status": det_data.status,
                 "ai_status": ai_data.status, "detections": len(det_data.detections)},
        ip_address=actor_ip,
    )
    record_event(
        db, action=AuditAction.AI_ANALYSIS_RECORDED, entity_type="inspection", entity_id=inspection.id,
        actor_id=None, actor_role="SYSTEM",
        details={"provider": ai_data.provider, "model": ai_data.model, "status": ai_data.status},
    )
    record_event(
        db, action=AuditAction.DECISION_RECORDED, entity_type="return", entity_id=return_record.id,
        actor_id=None, actor_role="SYSTEM",
        details={"outcome": result.outcome, "disposition": result.disposition,
                 "inspection_id": inspection.id, "engine": decision_service.ENGINE_VERSION},
    )
    db.flush()
    return inspection


def _safe_run(fn, path, label: str, fallback):
    try:
        return fn(path)
    except Exception:  # pragma: no cover - the services trap internally already
        logger.exception("%s stage crashed", label)
        return fallback
