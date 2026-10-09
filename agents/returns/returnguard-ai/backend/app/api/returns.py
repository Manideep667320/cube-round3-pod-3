"""Return management API (admin) and agent-facing return listings."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import client_ip, get_current_user, require_admin, require_agent
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models import (
    AuditAction,
    ExpectedComponent,
    Inspection,
    OTPChallenge,
    ReturnRecord,
    ReturnStatus,
    User,
    UserRole,
)
from app.schemas import (
    ExpectedComponentOut,
    OTPChallengeSummary,
    QRAuthOut,
    ReturnCreateRequest,
    ReturnDetailOut,
    ReturnOut,
    ReturnUpdateRequest,
)
from app.services.audit_service import record_event

router = APIRouter(prefix="/api/returns", tags=["returns"])

_COMPONENT_HINT_SEPARATOR = ","


def _generate_return_code(db: Session) -> str:
    for _ in range(50):
        code = f"RG-{secrets.token_hex(3).upper()}"
        if db.scalar(select(ReturnRecord.id).where(ReturnRecord.return_code == code)) is None:
            return code
    raise RuntimeError("Could not allocate a unique return code")


def _set_components(db: Session, ret: ReturnRecord, components) -> None:
    ret.expected_components.clear()
    db.flush()
    for comp in components:
        db.add(
            ExpectedComponent(
                return_id=ret.id,
                name=comp.name.strip(),
                yolo_class_hints=_COMPONENT_HINT_SEPARATOR.join(h.strip().lower() for h in comp.yolo_class_hints if h.strip()),
                ocr_text_hint=comp.ocr_text_hint.strip(),
            )
        )


def _otp_summaries(db: Session, return_id: str) -> list[OTPChallengeSummary]:
    rows = db.scalars(
        select(OTPChallenge).where(OTPChallenge.return_id == return_id).order_by(OTPChallenge.issued_at.desc())
    )
    return [
        OTPChallengeSummary(
            id=c.id, status=c.status, attempts=c.attempts,
            issued_at=c.issued_at, expires_at=c.expires_at, verified_at=c.verified_at,
        )
        for c in rows
    ]


def _inspection_summaries(db: Session, return_id: str) -> list[dict]:
    rows = db.scalars(
        select(Inspection).where(Inspection.return_id == return_id).order_by(Inspection.created_at.desc())
    )
    out = []
    for insp in rows:
        outcome = insp.decision.outcome if insp.decision is not None else None
        out.append({
            "id": insp.id,
            "status": insp.status,
            "created_at": insp.created_at,
            "completed_at": insp.completed_at,
            "decision_outcome": outcome,
            "image_url": f"/api/inspections/{insp.id}/image",
        })
    return out


# ---------------------------------------------------------------------------
# Admin CRUD
# ---------------------------------------------------------------------------
@router.get("", response_model=list[ReturnOut])
def list_returns(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(ReturnRecord).order_by(ReturnRecord.created_at.desc()))
    return list(rows)


@router.post("", response_model=ReturnOut, status_code=201)
def create_return(
    payload: ReturnCreateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    agent_id = None
    if payload.assigned_agent_id:
        agent = db.get(User, payload.assigned_agent_id)
        if agent is None or agent.role not in (UserRole.AGENT, UserRole.OPERATOR) or not agent.is_active:
            raise ConflictError("The assigned agent/operator does not exist or is inactive.", code="invalid_agent")
        agent_id = agent.id

    catalogue_product_id = None
    components = list(payload.expected_components)
    if payload.catalogue_product_id:
        from app.models import CatalogueProduct

        cat = db.get(CatalogueProduct, payload.catalogue_product_id)
        if cat is None:
            raise ConflictError("The referenced catalogue product does not exist.", code="invalid_catalogue")
        catalogue_product_id = cat.id
        if not components and cat.default_components:
            # Pre-fill expected components from the catalogue definition.
            from app.schemas import ExpectedComponentIn

            components = [ExpectedComponentIn(**c) for c in cat.default_components]

    ret = ReturnRecord(
        return_code=_generate_return_code(db),
        order_reference=payload.order_reference.strip(),
        expected_sku=payload.expected_sku.strip(),
        catalogue_product_id=catalogue_product_id,
        product_description=payload.product_description.strip(),
        assigned_agent_id=agent_id,
        status=ReturnStatus.PENDING,
        created_by_id=admin.id,
    )
    db.add(ret)
    db.flush()
    _set_components(db, ret, components)
    record_event(
        db,
        action=AuditAction.RETURN_CREATED,
        entity_type="return",
        entity_id=ret.id,
        actor_id=admin.id,
        actor_role=admin.role,
        details={"return_code": ret.return_code, "sku": ret.expected_sku, "agent_id": agent_id},
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(ret)
    return ret


@router.get("/{return_id}", response_model=ReturnDetailOut)
def get_return(return_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    ret = db.get(ReturnRecord, return_id)
    if ret is None:
        raise NotFoundError("Return not found.", code="not_found")
    detail = ReturnDetailOut(
        id=ret.id,
        return_code=ret.return_code,
        order_reference=ret.order_reference,
        expected_sku=ret.expected_sku,
        product_description=ret.product_description,
        status=ret.status,
        assigned_agent_id=ret.assigned_agent_id,
        created_by_id=ret.created_by_id,
        created_at=ret.created_at,
        updated_at=ret.updated_at,
        expected_components=[ExpectedComponentOut.model_validate(c) for c in ret.expected_components],
        qr_authorizations=[QRAuthOut.model_validate(a) for a in ret.qr_authorizations],
        otp_summary=_otp_summaries(db, return_id),
        inspections=_inspection_summaries(db, return_id),
    )
    return detail


@router.put("/{return_id}", response_model=ReturnOut)
def update_return(
    return_id: str,
    payload: ReturnUpdateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ret = db.get(ReturnRecord, return_id)
    if ret is None:
        raise NotFoundError("Return not found.", code="not_found")
    if ret.status in ReturnStatus.TERMINAL:
        raise ConflictError("This return is closed and cannot be edited.", code="return_closed")

    if payload.product_description is not None:
        ret.product_description = payload.product_description.strip()
    if payload.assigned_agent_id is not None:
        agent = db.get(User, payload.assigned_agent_id)
        if agent is None or agent.role != UserRole.AGENT or not agent.is_active:
            raise ConflictError("The assigned agent does not exist or is inactive.", code="invalid_agent")
        if ret.assigned_agent_id != agent.id:
            ret.assigned_agent_id = agent.id
            # Reassignment invalidates any active QR (bound to previous agent flow).
            now = datetime.now(timezone.utc)
            for auth in ret.qr_authorizations:
                if auth.status == "ACTIVE":
                    auth.status = "REVOKED"
                    auth.revoked_at = auth.revoked_at or now
                    auth.revoked_by_id = admin.id
            if ret.status == ReturnStatus.AWAITING_SCAN:
                ret.status = ReturnStatus.PENDING
    if payload.expected_components is not None:
        _set_components(db, ret, payload.expected_components)
    record_event(
        db,
        action=AuditAction.RETURN_UPDATED,
        entity_type="return",
        entity_id=ret.id,
        actor_id=admin.id,
        actor_role=admin.role,
        details={"return_code": ret.return_code},
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(ret)
    return ret


@router.post("/{return_id}/cancel", response_model=ReturnOut)
def cancel_return(
    return_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ret = db.get(ReturnRecord, return_id)
    if ret is None:
        raise NotFoundError("Return not found.", code="not_found")
    if ret.status in ReturnStatus.TERMINAL:
        raise ConflictError("This return is already closed.", code="return_closed")
    now = datetime.now(timezone.utc)
    for auth in ret.qr_authorizations:
        if auth.status == "ACTIVE":
            auth.status = "REVOKED"
            auth.revoked_at = auth.revoked_at or now
            auth.revoked_by_id = admin.id
    ret.status = ReturnStatus.CANCELLED
    record_event(
        db,
        action=AuditAction.RETURN_CANCELLED,
        entity_type="return",
        entity_id=ret.id,
        actor_id=admin.id,
        actor_role=admin.role,
        details={"return_code": ret.return_code},
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(ret)
    return ret


# ---------------------------------------------------------------------------
# Agent-facing
# ---------------------------------------------------------------------------
@router.get("/me/assigned", response_model=list[ReturnOut])
def list_assigned(_: User = Depends(require_agent), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(
        select(ReturnRecord)
        .where(ReturnRecord.assigned_agent_id == user.id)
        .order_by(ReturnRecord.created_at.desc())
    )
    return list(rows)
