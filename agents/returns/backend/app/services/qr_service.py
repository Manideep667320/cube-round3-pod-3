"""Hidden QR authorization service.

The QR image encodes only an opaque high-entropy token bound to one return.
No OTP, credentials, phone numbers or personal data are embedded.
Only the SHA-256 hash of the token is persisted.
"""
from __future__ import annotations

import base64
import io
from datetime import datetime, timedelta, timezone

import qrcode
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from agents.returns.backend.app.core.config import settings
from agents.returns.backend.app.core.errors import ConflictError, ForbiddenError, NotFoundError
from agents.returns.backend.app.core.security import create_scan_token, generate_high_entropy_token, hash_token
from agents.returns.backend.app.models import QRAuthorization, ReturnRecord, ReturnStatus, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def scan_value_for_token(token: str) -> str:
    """Value encoded in the QR image. Deliberately scheme-based and opaque."""
    return f"returnguard://scan?token={token}"


def render_qr_png_base64(scan_value: str) -> str:
    img = qrcode.make(scan_value, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def create_qr_authorization(
    db: Session, return_record: ReturnRecord, creator: User
) -> tuple[QRAuthorization, str]:
    """Create a fresh single-use QR authorization; returns (record, raw_token).

    Any previous ACTIVE authorization for the return is revoked first so only
    one live QR exists per return.
    """
    if return_record.status in ReturnStatus.TERMINAL:
        raise ConflictError("Cannot generate a QR for a closed return.", code="return_closed")
    if return_record.assigned_agent_id is None:
        raise ConflictError("Assign a delivery agent before generating a QR.", code="agent_required")

    now = _utcnow()
    for old in return_record.qr_authorizations:
        if old.status == "ACTIVE":
            old.status = "REVOKED"
            old.revoked_at = now
            old.revoked_by_id = creator.id

    raw_token = generate_high_entropy_token(32)
    auth = QRAuthorization(
        return_id=return_record.id,
        token_hash=hash_token(raw_token),
        token_prefix=raw_token[:8],
        status="ACTIVE",
        created_by_id=creator.id,
        expires_at=_utcnow() + timedelta(hours=settings.qr_token_ttl_hours),
    )
    db.add(auth)
    return_record.status = ReturnStatus.AWAITING_SCAN
    db.flush()
    return auth, raw_token


def list_qr_for_return(db: Session, return_id: str) -> list[QRAuthorization]:
    return list(
        db.scalars(
            select(QRAuthorization)
            .where(QRAuthorization.return_id == return_id)
            .order_by(QRAuthorization.created_at.desc())
        )
    )


def revoke_qr_authorization(db: Session, auth: QRAuthorization, actor: User) -> QRAuthorization:
    if auth.status != "ACTIVE":
        raise ConflictError("Only active QR authorizations can be revoked.", code="qr_not_active")
    now = _utcnow()
    result = db.execute(
        update(QRAuthorization)
        .where(QRAuthorization.id == auth.id, QRAuthorization.status == "ACTIVE")
        .values(status="REVOKED", revoked_at=now, revoked_by_id=actor.id)
    )
    if result.rowcount != 1:
        raise ConflictError("QR authorization was concurrently modified.", code="conflict")
    ret = db.get(ReturnRecord, auth.return_id)
    if ret is not None and ret.status == ReturnStatus.AWAITING_SCAN:
        ret.status = ReturnStatus.PENDING
    db.flush()
    return auth


def consume_qr_for_scan(db: Session, raw_token: str, agent: User) -> tuple[QRAuthorization, ReturnRecord]:
    """Validate a scanned token for this agent and atomically consume it.

    Enforces: token exists, is ACTIVE, not expired, return is assigned to this
    agent, and the return is still scannable. Replay of a consumed token fails.
    """
    token_hash = hash_token(raw_token)
    auth = db.scalar(select(QRAuthorization).where(QRAuthorization.token_hash == token_hash))
    if auth is None:
        raise NotFoundError("QR authorization not found.", code="qr_invalid")

    if auth.status == "ACTIVE" and ensure_utc(auth.expires_at) <= _utcnow():
        auth.status = "EXPIRED"
        db.flush()

    if auth.status == "EXPIRED":
        raise ConflictError("This QR authorization has expired.", code="qr_expired")
    if auth.status == "REVOKED":
        raise ConflictError("This QR authorization has been revoked.", code="qr_revoked")
    if auth.status == "USED":
        raise ConflictError("This QR authorization was already used.", code="qr_replayed")

    ret = db.get(ReturnRecord, auth.return_id)
    if ret is None:
        raise NotFoundError("Return not found.", code="not_found")
    if ret.status in ReturnStatus.TERMINAL:
        raise ConflictError("This return is closed.", code="return_closed")
    if ret.assigned_agent_id != agent.id:
        # Do not disclose the existence of someone else's return.
        raise ForbiddenError("This return is not assigned to you.", code="not_assigned")

    now = _utcnow()
    result = db.execute(
        update(QRAuthorization)
        .where(QRAuthorization.id == auth.id, QRAuthorization.status == "ACTIVE")
        .values(status="USED", used_at=now, used_by_agent_id=agent.id)
    )
    if result.rowcount != 1:
        raise ConflictError("This QR authorization was already used.", code="qr_replayed")

    ret.status = ReturnStatus.AWAITING_OTP
    db.flush()
    return auth, ret


def get_scan_token(auth: QRAuthorization, ret: ReturnRecord, agent: User) -> str:
    return create_scan_token(return_id=ret.id, agent_id=agent.id, qr_auth_id=auth.id)
