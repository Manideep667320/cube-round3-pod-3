"""Human review, audit history and operational statistics endpoints (admin)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import client_ip, require_admin
from app.core.errors import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import (
    AuditAction,
    Decision,
    DetectionRun,
    HumanReview,
    Inspection,
    OCRResult,
    OTPChallenge,
    ReturnRecord,
    ReturnStatus,
    User,
    UserRole,
)
from app.schemas import AuditEventOut, ReviewOut, ReviewResolveRequest, StatsOut
from app.services.audit_service import list_events, record_event

router = APIRouter(prefix="/api", tags=["review-audit"])


def _inspection_summary_dict(db: Session, inspection: Inspection) -> dict:
    outcome = inspection.decision.outcome if inspection.decision is not None else None
    return {
        "id": inspection.id,
        "return_id": inspection.return_id,
        "agent_id": inspection.agent_id,
        "status": inspection.status,
        "created_at": inspection.created_at,
        "completed_at": inspection.completed_at,
        "decision_outcome": outcome,
        "image_url": f"/api/inspections/{inspection.id}/image",
        "ocr_status": inspection.ocr_result.status if inspection.ocr_result else None,
        "detection_status": inspection.detection_run.status if inspection.detection_run else None,
    }


@router.get("/review-queue", response_model=list[dict])
def review_queue(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Returns whose latest automated decision was MANUAL_REVIEW (plus stale INSPECTED)."""
    rows = db.scalars(
        select(Inspection)
        .join(Decision, Decision.inspection_id == Inspection.id)
        .where(Decision.outcome == "MANUAL_REVIEW")
        .order_by(Inspection.created_at.desc())
    )
    out = []
    for inspection in rows:
        ret = db.get(ReturnRecord, inspection.return_id)
        if ret is None or ret.status != ReturnStatus.NEEDS_REVIEW:
            continue
        summary = _inspection_summary_dict(db, inspection)
        summary["return_code"] = ret.return_code
        summary["expected_sku"] = ret.expected_sku
        summary["product_description"] = ret.product_description
        out.append(summary)
    return out


@router.post("/inspections/{inspection_id}/resolve", response_model=ReviewOut, status_code=201)
def resolve_review(
    inspection_id: str,
    payload: ReviewResolveRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise NotFoundError("Inspection not found.", code="not_found")
    ret = db.get(ReturnRecord, inspection.return_id)
    if ret is None:
        raise NotFoundError("Return not found.", code="not_found")
    if ret.status != ReturnStatus.NEEDS_REVIEW:
        raise ConflictError("This return is not awaiting review.", code="not_in_review")
    automated = inspection.decision.outcome if inspection.decision is not None else None

    review = HumanReview(
        inspection_id=inspection.id,
        return_id=ret.id,
        reviewer_id=admin.id,
        outcome=payload.outcome,
        reason=payload.reason.strip(),
        overrides_automated=(automated is not None and automated != payload.outcome),
    )
    db.add(review)
    # The original automated decision row is intentionally preserved untouched.
    ret.status = ReturnStatus.APPROVED if payload.outcome == "APPROVE" else ReturnStatus.REJECTED
    record_event(
        db,
        action=AuditAction.REVIEW_RESOLVED,
        entity_type="return",
        entity_id=ret.id,
        actor_id=admin.id,
        actor_role=admin.role,
        details={
            "inspection_id": inspection.id,
            "outcome": payload.outcome,
            "automated_outcome": automated,
            "overrides_automated": review.overrides_automated,
        },
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(review)
    return review


@router.get("/audit", response_model=list[AuditEventOut])
def audit_history(
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_events(db, entity_type=entity_type, entity_id=entity_id, action=action, limit=limit, offset=offset)


@router.get("/stats", response_model=StatsOut)
def stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    returns_by_status = {
        status: db.scalar(select(func.count(ReturnRecord.id)).where(ReturnRecord.status == status)) or 0
        for status in ReturnStatus.ALL
    }
    decisions = {
        outcome: db.scalar(
            select(func.count(Decision.id))
            .join(Inspection, Inspection.id == Decision.inspection_id)
            .join(ReturnRecord, ReturnRecord.id == Inspection.return_id)
            .where(ReturnRecord.status.in_(ReturnStatus.ALL))
            .where(Decision.outcome == outcome)
        )
        or 0
        for outcome in ("APPROVE", "REJECT", "MANUAL_REVIEW")
    }
    otp_by_status = {
        status: db.scalar(select(func.count(OTPChallenge.id)).where(OTPChallenge.status == status)) or 0
        for status in ("PENDING", "VERIFIED", "EXPIRED", "EXHAUSTED", "SUPERSEDED")
    }
    return StatsOut(
        returns_by_status=returns_by_status,
        total_returns=db.scalar(select(func.count(ReturnRecord.id))) or 0,
        total_inspections=db.scalar(select(func.count(Inspection.id))) or 0,
        decisions=decisions,
        otp_challenges=otp_by_status,
        agents=db.scalar(select(func.count(User.id)).where(User.role == UserRole.AGENT)) or 0,
    )
