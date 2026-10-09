"""OTP challenge service.

Guarantees:
- 6-digit code from `secrets`, HMAC-hashed at rest (never persisted in plaintext).
- 5-minute default expiry, attempt cap, resend cooldown and hourly issue cap.
- Issuing a replacement invalidates the previous challenge (SUPERSEDED).
- Verification and consumption are atomic single-row state transitions, so
  replay and concurrent verification cannot both succeed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.security import generate_otp_code, hash_otp, verify_otp_hash
from app.models import OTPChallenge, ReturnRecord, ReturnStatus, User
from app.services.audit_service import record_event
from app.services.sms_service import SMSProviderError, get_sms_provider, mask_phone

logger = logging.getLogger("returnguard.otp")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def latest_pending_challenge(db: Session, return_id: str, agent_id: str) -> OTPChallenge | None:
    return db.scalar(
        select(OTPChallenge)
        .where(
            OTPChallenge.return_id == return_id,
            OTPChallenge.agent_id == agent_id,
            OTPChallenge.status == "PENDING",
        )
        .order_by(OTPChallenge.issued_at.desc())
        .limit(1)
    )


def issue_otp(db: Session, ret: ReturnRecord, agent: User, actor_ip: str | None = None) -> tuple[OTPChallenge, datetime]:
    """Generate and deliver a fresh OTP to the agent's verified phone.

    Returns (challenge, resend_available_at). Raises AppError on provider failure
    (never silently falls back to the mock provider).
    """
    if not agent.phone or not agent.phone_verified or not agent.is_active:
        raise ConflictError(
            "No verified phone number is registered for this agent. Ask an administrator to verify it.",
            code="phone_unverified",
        )

    now = _utcnow()
    existing = latest_pending_challenge(db, ret.id, agent.id)
    if existing is not None:
        issued = _aware(existing.issued_at)
        if issued is not None:
            cooldown = timedelta(seconds=settings.otp_resend_cooldown_seconds)
            if now - issued < cooldown:
                raise AppError(
                    "Please wait before requesting another code.", code="resend_cooldown", status_code=429
                )

    # Hourly issue cap (bounded resend behavior).
    window_start = now - timedelta(hours=1)
    issues_last_hour = db.scalar(
        select(func.count(OTPChallenge.id)).where(
            OTPChallenge.return_id == ret.id,
            OTPChallenge.agent_id == agent.id,
            OTPChallenge.issued_at >= window_start,
        )
    ) or 0
    if issues_last_hour >= settings.otp_max_issues_per_hour:
        raise AppError("Too many verification codes requested. Try again later.", code="otp_rate_limited", status_code=429)

    # Invalidate any previous pending challenge (previous OTP invalidation).
    if existing is not None:
        db.execute(
            update(OTPChallenge)
            .where(OTPChallenge.id == existing.id, OTPChallenge.status == "PENDING")
            .values(status="SUPERSEDED", superseded_at=now)
        )

    code = generate_otp_code(6)
    challenge = OTPChallenge(
        return_id=ret.id,
        agent_id=agent.id,
        qr_auth_id=_latest_qr_auth_id(db, ret),
        code_hash=hash_otp(code),
        status="PENDING",
        max_attempts=settings.otp_max_attempts,
        issued_at=now,
        expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
        issue_index=issues_last_hour + 1,
    )
    db.add(challenge)
    db.flush()

    body = f"ReturnGuard AI verification code: {code}. Valid for {settings.otp_ttl_seconds // 60} minutes. Do not share it."
    try:
        get_sms_provider().send(agent.phone, body)
    except SMSProviderError as exc:
        challenge.status = "SUPERSEDED"
        challenge.superseded_at = _utcnow()
        db.commit()
        logger.error("OTP delivery failed for return=%s agent=%s", ret.return_code, agent.username)
        raise AppError(
            "The verification code could not be sent. Please try again.",
            code="sms_delivery_failed",
            status_code=502,
        ) from exc

    record_event(
        db,
        action="OTP_ISSUED",
        entity_type="otp_challenge",
        entity_id=challenge.id,
        actor_id=agent.id,
        actor_role=agent.role,
        details={"return_code": ret.return_code, "masked_phone": mask_phone(agent.phone)},
        ip_address=actor_ip,
    )
    resend_available_at = now + timedelta(seconds=settings.otp_resend_cooldown_seconds)
    return challenge, resend_available_at


def _latest_qr_auth_id(db: Session, ret: ReturnRecord) -> str:
    from app.models import QRAuthorization

    auth = db.scalar(
        select(QRAuthorization)
        .where(QRAuthorization.return_id == ret.id, QRAuthorization.status == "USED")
        .order_by(QRAuthorization.used_at.desc())
        .limit(1)
    )
    if auth is None:
        raise ConflictError("Scan state not found for this return.", code="qr_state_missing")
    return auth.id


def verify_otp(db: Session, ret: ReturnRecord, agent: User, code: str, actor_ip: str | None = None) -> OTPChallenge:
    """Verify and atomically consume the pending OTP challenge.

    On success the challenge transitions PENDING -> VERIFIED exactly once.
    Wrong codes increment the attempt counter atomically; hitting the cap
    exhausts the challenge.
    """
    now = _utcnow()
    challenge = latest_pending_challenge(db, ret.id, agent.id)
    if challenge is None:
        raise NotFoundError("No active verification code. Request a new one.", code="otp_missing")

    expires = _aware(challenge.expires_at)
    if expires is not None and expires <= now:
        db.execute(
            update(OTPChallenge)
            .where(OTPChallenge.id == challenge.id, OTPChallenge.status == "PENDING")
            .values(status="EXPIRED")
        )
        db.commit()  # persist expiry even though we return an error response
        raise AppError("The verification code has expired. Request a new one.", code="otp_expired", status_code=410)

    # Atomically claim an attempt; prevents concurrent double-verification.
    claimed = db.execute(
        update(OTPChallenge)
        .where(OTPChallenge.id == challenge.id, OTPChallenge.status == "PENDING")
        .values(attempts=OTPChallenge.attempts + 1)
    )
    if claimed.rowcount != 1:
        raise AppError("The verification code has expired. Request a new one.", code="otp_consumed", status_code=410)
    db.refresh(challenge)
    # Persist the claimed attempt immediately: failed attempts must survive the
    # error response (a rollback here would let attackers retry indefinitely).
    db.commit()

    if verify_otp_hash(code, challenge.code_hash):
        consumed = db.execute(
            update(OTPChallenge)
            .where(OTPChallenge.id == challenge.id, OTPChallenge.status == "PENDING")
            .values(status="VERIFIED", verified_at=now, consumed_at=now)
        )
        if consumed.rowcount != 1:
            # Another request consumed it first.
            raise AppError("The verification code has expired. Request a new one.", code="otp_consumed", status_code=410)
        ret.status = ReturnStatus.AWAITING_INSPECTION
        record_event(
            db,
            action="OTP_VERIFIED",
            entity_type="otp_challenge",
            entity_id=challenge.id,
            actor_id=agent.id,
            actor_role=agent.role,
            details={"return_code": ret.return_code},
            ip_address=actor_ip,
        )
        db.flush()
        return challenge

    # Wrong code: exhaust the challenge if the cap is reached.
    if challenge.attempts >= challenge.max_attempts:
        db.execute(
            update(OTPChallenge)
            .where(OTPChallenge.id == challenge.id, OTPChallenge.status == "PENDING")
            .values(status="EXHAUSTED")
        )
        db.flush()
        record_event(
            db,
            action="OTP_VERIFY_FAILED",
            entity_type="otp_challenge",
            entity_id=challenge.id,
            actor_id=agent.id,
            actor_role=agent.role,
            details={"return_code": ret.return_code, "reason": "exhausted"},
            ip_address=actor_ip,
        )
        db.commit()
        raise AppError("Too many incorrect attempts. Request a new code.", code="otp_exhausted", status_code=410)

    record_event(
        db,
        action="OTP_VERIFY_FAILED",
        entity_type="otp_challenge",
        entity_id=challenge.id,
        actor_id=agent.id,
        actor_role=agent.role,
        details={"return_code": ret.return_code, "attempts": challenge.attempts},
        ip_address=actor_ip,
    )
    db.commit()
    # Generic error: never reveal whether the code was close.
    raise AppError("Incorrect verification code.", code="otp_incorrect", status_code=400)
