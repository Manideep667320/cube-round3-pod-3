"""Authentication API: login and current-session endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.returns.backend.app.auth.deps import client_ip, get_current_user
from agents.returns.backend.app.core.config import settings
from agents.returns.backend.app.core.errors import AppError, AuthError
from agents.returns.backend.app.core.ratelimit import login_limiter
from agents.returns.backend.app.core.security import create_access_token, verify_password
from agents.returns.backend.app.db.session import get_db
from agents.returns.backend.app.models import AuditAction, User
from agents.returns.backend.app.schemas import LoginRequest, TokenResponse, UserOut
from agents.returns.backend.app.services.audit_service import record_event

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request) or "unknown"
    limiter_key = f"login:{ip}:{payload.username.lower()}"
    if not login_limiter.check(
        limiter_key, settings.login_rate_limit_attempts, settings.login_rate_limit_window_seconds
    ):
        raise AppError("Too many sign-in attempts. Please try again later.", code="rate_limited", status_code=429)

    user = db.scalar(select(User).where(User.username == payload.username.lower()))
    # Constant-shape failure: same error whether the user exists or not.
    if user is None or not verify_password(payload.password, user.password_hash) or not user.is_active:
        if user is not None:
            record_event(
                db,
                action=AuditAction.LOGIN_FAILURE,
                entity_type="user",
                entity_id=user.id,
                actor_id=user.id,
                actor_role=user.role,
                details={"reason": "bad_credentials_or_inactive"},
                ip_address=ip,
            )
            db.commit()
        raise AuthError("Invalid username or password.", code="invalid_credentials")

    record_event(
        db,
        action=AuditAction.LOGIN_SUCCESS,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        actor_role=user.role,
        details={},
        ip_address=ip,
    )
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, user.role), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
