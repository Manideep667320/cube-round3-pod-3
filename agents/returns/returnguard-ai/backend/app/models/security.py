"""QR authorization and OTP challenge models.

Security invariants enforced here and in the services layer:
- Only hashes of QR secrets and OTP codes are persisted; raw values never are.
- QR authorizations are single-use and bound to one return.
- OTP challenges are single-use, expiring, attempt-bounded and superseded on resend.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class QRAuthorization(Base):
    __tablename__ = "qr_authorizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    return_id: Mapped[str] = mapped_column(String(36), ForeignKey("returns.id"), nullable=False, index=True)
    # SHA-256 of the raw token; the raw token is shown exactly once at creation
    # (rendered into the printable QR image) and never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # Non-secret display prefix so admins can identify a printed QR without retrieving the secret.
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False, index=True)
    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by_agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    return_record: Mapped["ReturnRecord"] = relationship(back_populates="qr_authorizations")  # noqa: F821


class OTPChallenge(Base):
    __tablename__ = "otp_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    return_id: Mapped[str] = mapped_column(String(36), ForeignKey("returns.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    qr_auth_id: Mapped[str] = mapped_column(String(36), ForeignKey("qr_authorizations.id"), nullable=False)
    # HMAC-SHA256 of the six-digit code keyed with SECRET_KEY; raw code never stored.
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issue_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OTPChallenge {self.id} status={self.status} attempts={self.attempts}>"
