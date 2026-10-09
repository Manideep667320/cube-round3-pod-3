"""Admin user management. There is NO public registration path."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import client_ip, require_admin
from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_password
from app.db.session import get_db
from app.models import AuditAction, User, UserRole
from app.schemas import UserCreateRequest, UserOut, UserUpdateRequest
from app.services.audit_service import record_event

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


@router.get("", response_model=list[UserOut])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.created_at.desc())))


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    username = payload.username.lower()
    exists = db.scalar(select(User).where(User.username == username))
    if exists is not None:
        raise ConflictError("A user with this username already exists.", code="username_taken")
    user = User(
        username=username,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role if payload.role in UserRole.ALL else UserRole.AGENT,
        phone=payload.phone,
        phone_verified=bool(payload.phone and payload.phone_verified),
        is_active=True,
    )
    db.add(user)
    db.flush()
    record_event(
        db,
        action=AuditAction.USER_CREATED,
        entity_type="user",
        entity_id=user.id,
        actor_id=admin.id,
        actor_role=admin.role,
        details={"username": username, "role": user.role, "phone_verified": user.phone_verified},
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.", code="not_found")
    changes: dict[str, str] = {}
    if payload.full_name is not None:
        user.full_name = payload.full_name
        changes["full_name"] = "updated"
    if payload.phone is not None:
        phone_changed = (payload.phone or None) != user.phone
        user.phone = payload.phone or None
        # Any phone change requires re-verification by an admin.
        if phone_changed:
            user.phone_verified = False
        changes["phone"] = "updated"
    if payload.phone_verified is not None:
        if payload.phone_verified and not user.phone:
            raise ConflictError("Set a phone number before marking it verified.", code="phone_required")
        user.phone_verified = payload.phone_verified
        changes["phone_verified"] = str(payload.phone_verified)
    if payload.is_active is not None:
        user.is_active = payload.is_active
        changes["is_active"] = str(payload.is_active)
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
        changes["password"] = "rotated"
    db.flush()
    record_event(
        db,
        action=AuditAction.USER_UPDATED,
        entity_type="user",
        entity_id=user.id,
        actor_id=admin.id,
        actor_role=admin.role,
        details=changes,
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return user
