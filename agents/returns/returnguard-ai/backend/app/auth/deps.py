"""Authentication and authorization dependencies.

All role/ownership enforcement happens here and in the services layer; the
frontend is never trusted for authorization.
"""
from __future__ import annotations

from dataclasses import dataclass

import jwt as pyjwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import AuthError, ForbiddenError, NotFoundError
from app.core.security import decode_token
from app.db.session import get_db
from app.models import ReturnRecord, User


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def _user_from_token(db: Session, token: str, purpose: str = "access") -> User:
    try:
        payload = decode_token(token, expected_purpose=purpose)
    except pyjwt.ExpiredSignatureError as exc:
        raise AuthError("Session expired. Please sign in again.", code="token_expired") from exc
    except pyjwt.PyJWTError as exc:
        raise AuthError("Invalid authentication token.", code="invalid_token") from exc
    user = db.get(User, payload.get("sub", ""))
    if user is None or not user.is_active:
        raise AuthError("Authentication failed.", code="auth_failed")
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthError("Missing bearer token.", code="missing_token")
    return _user_from_token(db, auth.removeprefix("Bearer ").strip())


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise ForbiddenError("Administrator access required.", code="admin_required")
    return user


def require_agent(user: User = Depends(get_current_user)) -> User:
    """Backward-compatible alias for require_inspector."""
    return require_inspector(user)


def require_inspector(user: User = Depends(get_current_user)) -> User:
    """Delivery agents AND warehouse inspection operators may run inspections
    on their assigned returns. Everything else stays admin-only."""
    if user.role not in ("AGENT", "OPERATOR"):
        raise ForbiddenError("Inspection access required (delivery agent or operator).", code="inspector_required")
    return user


@dataclass
class ScanContext:
    user: User
    return_record: ReturnRecord
    qr_auth_id: str
    otp_challenge_id: str | None = None


def get_scan_context(request: Request, db: Session = Depends(get_db)) -> ScanContext:
    """Resolve a short-lived scan token (issued after a successful QR scan)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthError("Missing bearer token.", code="missing_token")
    token = auth.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token, expected_purpose="scan")
    except pyjwt.ExpiredSignatureError as exc:
        raise AuthError("Scan session expired. Scan the QR code again.", code="scan_expired") from exc
    except pyjwt.PyJWTError as exc:
        raise AuthError("Invalid scan token.", code="invalid_token") from exc

    user = db.get(User, payload.get("sub", ""))
    if user is None or not user.is_active or user.role not in ("AGENT", "OPERATOR"):
        raise AuthError("Authentication failed.", code="auth_failed")
    ret = db.get(ReturnRecord, payload.get("rid", ""))
    if ret is None:
        raise NotFoundError("Return not found.", code="not_found")
    if ret.assigned_agent_id != user.id:
        raise ForbiddenError("This return is not assigned to you.", code="not_assigned")
    return ScanContext(user=user, return_record=ret, qr_auth_id=payload.get("qid", ""))


@dataclass
class InspectionContext:
    user: User
    return_record: ReturnRecord
    otp_challenge_id: str


def get_inspection_context(request: Request, db: Session = Depends(get_db)) -> InspectionContext:
    """Resolve an inspection token (issued only after OTP verification)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthError("Missing bearer token.", code="missing_token")
    token = auth.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token, expected_purpose="inspection")
    except pyjwt.ExpiredSignatureError as exc:
        raise AuthError("Inspection session expired. Scan and verify again.", code="inspection_expired") from exc
    except pyjwt.PyJWTError as exc:
        raise AuthError("Invalid inspection token.", code="invalid_token") from exc

    user = db.get(User, payload.get("sub", ""))
    if user is None or not user.is_active or user.role not in ("AGENT", "OPERATOR"):
        raise AuthError("Authentication failed.", code="auth_failed")
    ret = db.get(ReturnRecord, payload.get("rid", ""))
    if ret is None:
        raise NotFoundError("Return not found.", code="not_found")
    if ret.assigned_agent_id != user.id:
        raise ForbiddenError("This return is not assigned to you.", code="not_assigned")
    return InspectionContext(user=user, return_record=ret, otp_challenge_id=payload.get("cid", ""))
