"""Audit trail service: appends and queries audit events.

Rules:
- Never persist secrets (raw QR tokens, OTP codes, passwords) in details.
- Actor identifiers come from the authenticated session, not the client body.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent

_SENSITIVE_KEYS = {"token", "code", "otp", "password", "secret", "qr_token", "scan_token", "inspection_token"}


def _scrub(details: dict[str, Any]) -> dict[str, Any]:
    return {k: ("[REDACTED]" if k.lower() in _SENSITIVE_KEYS else v) for k, v in details.items()}


def record_event(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_id: str | None = None,
    actor_role: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=_scrub(details or {}),
        ip_address=ip_address,
    )
    db.add(event)
    db.flush()
    return event


def list_events(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id)
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    stmt = stmt.limit(min(limit, 500)).offset(max(offset, 0))
    return list(db.scalars(stmt))
