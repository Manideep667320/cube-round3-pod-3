"""Inspection API: authenticated image upload, results and image serving."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import (
    InspectionContext,
    client_ip,
    get_current_user,
    get_inspection_context,
    require_admin,
)
from app.core.errors import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import HumanReview, Inspection, ReturnRecord, User
from app.schemas import InspectionDetailOut
from app.services import image_service, inspection_service
from app.services.audit_service import record_event

router = APIRouter(prefix="/api/inspections", tags=["inspections"])


def _image_url(inspection_id: str) -> str:
    return f"/api/inspections/{inspection_id}/image"


def _serialize_detail(db: Session, inspection: Inspection, return_record: ReturnRecord) -> InspectionDetailOut:
    reviews = db.scalars(
        select(HumanReview)
        .where(HumanReview.inspection_id == inspection.id)
        .order_by(HumanReview.created_at.desc())
    )
    return InspectionDetailOut(
        id=inspection.id,
        return_id=inspection.return_id,
        return_code=return_record.return_code,
        agent_id=inspection.agent_id,
        status=inspection.status,
        view_type=inspection.view_type,
        created_at=inspection.created_at,
        completed_at=inspection.completed_at,
        error_message=inspection.error_message,
        image={
            "url": _image_url(inspection.id),
            "original_name": inspection.image_original_name,
            "content_type": inspection.image_content_type,
            "size_bytes": inspection.image_size_bytes,
            "sha256": inspection.image_sha256,
            "width": inspection.image_width,
            "height": inspection.image_height,
        },
        ocr=inspection.ocr_result,
        detection_run=inspection.detection_run,
        ai_analysis=inspection.ai_analysis,
        evidence=inspection.evidence,
        decision=inspection.decision,
        reviews=list(reviews),
    )


@router.post("", response_model=InspectionDetailOut, status_code=201)
async def upload_and_inspect(
    request: Request,
    file: UploadFile = File(...),
    view_type: str = Form("STANDARD"),
    db: Session = Depends(get_db),
    ctx: InspectionContext = Depends(get_inspection_context),
):
    """Upload a product photo and run the full inspection pipeline.

    Requires a valid inspection token (issued only after OTP verification).
    `view_type=CONTENTS_LAYOUT` marks a photo showing ALL returned contents
    laid out - the only single-photo evidence that can confirm a missing part.
    Multiple photos may be added per return; decisions aggregate across them.
    """
    data = await file.read()
    stored = image_service.validate_and_store(
        data=data,
        return_id=ctx.return_record.id,
        original_name=file.filename or "upload",
    )
    # Duplicate-submission guard: identical bytes already inspected for this return.
    from sqlalchemy import select as _select
    from app.models import Inspection as _Inspection

    dup = db.scalar(
        _select(_Inspection).where(
            _Inspection.return_id == ctx.return_record.id,
            _Inspection.image_sha256 == stored.sha256,
        )
    )
    if dup is not None:
        raise ConflictError(
            "This exact photo was already submitted for this return.", code="duplicate_upload"
        )
    inspection = inspection_service.create_inspection(
        db,
        return_record=ctx.return_record,
        agent=ctx.user,
        stored=stored,
        otp_challenge_id=ctx.otp_challenge_id,
        view_type=view_type,
        actor_ip=client_ip(request),
    )
    db.commit()
    db.refresh(inspection)
    return _serialize_detail(db, inspection, ctx.return_record)


def _load_inspection_for_admin(db: Session, inspection_id: str) -> tuple[Inspection, ReturnRecord]:
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise NotFoundError("Inspection not found.", code="not_found")
    ret = db.get(ReturnRecord, inspection.return_id)
    if ret is None:
        raise NotFoundError("Return not found.", code="not_found")
    return inspection, ret


def _load_inspection_for_agent(db: Session, inspection_id: str, agent: User) -> tuple[Inspection, ReturnRecord]:
    inspection, ret = _load_inspection_for_admin(db, inspection_id)
    if ret.assigned_agent_id != agent.id and inspection.agent_id != agent.id:
        raise NotFoundError("Inspection not found.", code="not_found")
    return inspection, ret


@router.get("/{inspection_id}", response_model=InspectionDetailOut)
def get_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "ADMIN":
        inspection, ret = _load_inspection_for_admin(db, inspection_id)
    else:
        inspection, ret = _load_inspection_for_agent(db, inspection_id, user)
    return _serialize_detail(db, inspection, ret)


@router.get("/{inspection_id}/image")
def get_inspection_image(
    inspection_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "ADMIN":
        inspection, _ret = _load_inspection_for_admin(db, inspection_id)
    else:
        inspection, _ret = _load_inspection_for_agent(db, inspection_id, user)
    path = image_service.resolve_stored_path(inspection.return_id, inspection.image_stored_name)
    return FileResponse(path, media_type=inspection.image_content_type or "image/jpeg")


__all__ = ["router"]
