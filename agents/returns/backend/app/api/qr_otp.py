"""QR authorization and OTP endpoints.

Flow: admin generates QR -> agent scans (camera or paste) -> agent requests
OTP -> agent verifies OTP -> inspection token issued.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from agents.returns.backend.app.auth.deps import ScanContext, client_ip, get_scan_context, require_admin, require_agent
from agents.returns.backend.app.core.errors import ConflictError, ForbiddenError, NotFoundError
from agents.returns.backend.app.core.security import create_inspection_token, decode_token
from agents.returns.backend.app.db.session import get_db
from agents.returns.backend.app.models import AuditAction, QRAuthorization, ReturnRecord, User
from agents.returns.backend.app.schemas import (
    OTPRequestOut,
    OTPVerifyRequest,
    OTPVerifyResponse,
    QRAuthOut,
    QRGenerateResponse,
    QRScanRequest,
    QRScanResponse,
)
from agents.returns.backend.app.services import otp_service, qr_service
from agents.returns.backend.app.services.audit_service import record_event
from agents.returns.backend.app.services.sms_service import mask_phone

import jwt as pyjwt

qr_router = APIRouter(prefix="/api/qr", tags=["qr"])
returns_qr_router = APIRouter(prefix="/api/returns/{return_id}/qr", tags=["qr"])
otp_router = APIRouter(prefix="/api/otp", tags=["otp"])


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


# ---------------------------------------------------------------------------
# Admin QR management
# ---------------------------------------------------------------------------
@qr_router.get("", response_model=list[dict])
def list_all_qr(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """All QR authorizations across returns (admin operations view)."""
    from sqlalchemy import select

    from agents.returns.backend.app.models import ReturnRecord

    rows = db.execute(
        select(QRAuthorization, ReturnRecord.return_code)
        .join(ReturnRecord, ReturnRecord.id == QRAuthorization.return_id)
        .order_by(QRAuthorization.created_at.desc())
    )
    return [
        {**QRAuthOut.model_validate(auth).model_dump(), "return_code": code}
        for auth, code in rows
    ]


@returns_qr_router.post("", response_model=QRGenerateResponse, status_code=201)
def generate_qr(
    return_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ret = db.get(ReturnRecord, return_id)
    if ret is None:
        raise NotFoundError("Return not found.", code="not_found")
    auth, raw_token = qr_service.create_qr_authorization(db, ret, admin)
    scan_value = qr_service.scan_value_for_token(raw_token)
    record_event(
        db,
        action=AuditAction.QR_GENERATED,
        entity_type="qr_authorization",
        entity_id=auth.id,
        actor_id=admin.id,
        actor_role=admin.role,
        details={"return_code": ret.return_code, "token_prefix": auth.token_prefix},
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(auth)
    return QRGenerateResponse(
        qr_authorization=QRAuthOut.model_validate(auth),
        token=raw_token,
        qr_png_base64=qr_service.render_qr_png_base64(scan_value),
        scan_value=scan_value,
    )


@returns_qr_router.get("", response_model=list[QRAuthOut])
def list_qr(return_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    ret = db.get(ReturnRecord, return_id)
    if ret is None:
        raise NotFoundError("Return not found.", code="not_found")
    return [QRAuthOut.model_validate(a) for a in qr_service.list_qr_for_return(db, return_id)]


@qr_router.post("/{qr_id}/revoke", response_model=QRAuthOut)
def revoke_qr(
    qr_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    auth = db.get(QRAuthorization, qr_id)
    if auth is None:
        raise NotFoundError("QR authorization not found.", code="not_found")
    auth = qr_service.revoke_qr_authorization(db, auth, admin)
    record_event(
        db,
        action=AuditAction.QR_REVOKED,
        entity_type="qr_authorization",
        entity_id=auth.id,
        actor_id=admin.id,
        actor_role=admin.role,
        details={"token_prefix": auth.token_prefix},
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(auth)
    return QRAuthOut.model_validate(auth)


# ---------------------------------------------------------------------------
# Agent scanning + OTP
# ---------------------------------------------------------------------------
@qr_router.post("/scan", response_model=QRScanResponse)
def scan_qr(
    payload: QRScanRequest,
    request: Request,
    agent: User = Depends(require_agent),
    db: Session = Depends(get_db),
):
    ip = client_ip(request)
    try:
        auth, ret = qr_service.consume_qr_for_scan(db, payload.token, agent)
    except Exception:
        record_event(
            db,
            action=AuditAction.QR_SCAN_REJECTED,
            entity_type="qr_authorization",
            entity_id="unknown",
            actor_id=agent.id,
            actor_role=agent.role,
            details={"reason": "invalid_or_unauthorized"},
            ip_address=ip,
        )
        db.commit()
        raise
    record_event(
        db,
        action=AuditAction.QR_SCANNED,
        entity_type="qr_authorization",
        entity_id=auth.id,
        actor_id=agent.id,
        actor_role=agent.role,
        details={"return_code": ret.return_code},
        ip_address=ip,
    )
    db.commit()
    return QRScanResponse(
        scan_token=qr_service.get_scan_token(auth, ret, agent),
        return_id=ret.id,
        return_code=ret.return_code,
        product_description=ret.product_description,
        assigned_agent_id=agent.id,
    )


@otp_router.post("/request", response_model=OTPRequestOut)
def request_otp(
    request: Request,
    scan: ScanContext = Depends(get_scan_context),
    db: Session = Depends(get_db),
):
    challenge, resend_available_at = otp_service.issue_otp(
        db, scan.return_record, scan.user, actor_ip=client_ip(request)
    )
    db.commit()
    return OTPRequestOut(
        masked_phone=mask_phone(scan.user.phone or ""),
        expires_at=_aware(challenge.expires_at),
        resend_available_at=resend_available_at,
        max_attempts=challenge.max_attempts,
    )


@otp_router.post("/verify", response_model=OTPVerifyResponse)
def verify_otp_endpoint(
    payload: OTPVerifyRequest,
    request: Request,
    agent: User = Depends(require_agent),
    db: Session = Depends(get_db),
):
    try:
        scan_payload = decode_token(payload.scan_token, expected_purpose="scan")
    except pyjwt.ExpiredSignatureError as exc:
        raise ConflictError("Scan session expired. Scan the QR code again.", code="scan_expired") from exc
    except pyjwt.PyJWTError as exc:
        raise ConflictError("Invalid scan session.", code="scan_invalid") from exc

    if scan_payload.get("sub") != agent.id:
        raise ForbiddenError("This scan session belongs to another agent.", code="scan_mismatch")
    ret = db.get(ReturnRecord, scan_payload.get("rid", ""))
    if ret is None:
        raise NotFoundError("Return not found.", code="not_found")
    if ret.assigned_agent_id != agent.id:
        raise ForbiddenError("This return is not assigned to you.", code="not_assigned")

    challenge = otp_service.verify_otp(db, ret, agent, payload.code, actor_ip=client_ip(request))
    inspection_token = create_inspection_token(return_id=ret.id, agent_id=agent.id, otp_challenge_id=challenge.id)
    db.commit()
    return OTPVerifyResponse(
        inspection_token=inspection_token, return_id=ret.id, return_code=ret.return_code
    )
