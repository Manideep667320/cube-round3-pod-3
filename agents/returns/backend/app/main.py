"""FastAPI application entrypoint.

Startup guarantees:
- Production REFUSES to boot with the mock SMS provider (no silent fallback).
- Database tables exist for SQLite local dev (Alembic migrations are the
  production path; see README).
- Optional one-time admin bootstrap from environment variables when no admin
  account exists yet.
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from agents.returns.backend.app.api import catalogue, health, inspections, qr_otp, review, returns, users
from agents.returns.backend.app.auth import router as auth_router
from agents.returns.backend.app.core.config import settings
from agents.returns.backend.app.core.errors import register_exception_handlers
from agents.returns.backend.app.db.session import Base, SessionLocal, engine
from agents.returns.backend.app.models import User, UserRole
from agents.returns.backend.app.core.security import hash_password
from agents.returns.backend.app.services.audit_service import record_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("returnguard")


def _ensure_production_safety() -> None:
    if settings.is_production and settings.sms_provider == "mock":
        raise RuntimeError(
            "Refusing to start: SMS_PROVIDER=mock is not allowed when APP_ENV=production. "
            "Configure a real SMS provider (e.g. Twilio)."
        )
    if settings.is_production and settings.secret_key == "CHANGE-ME-DEV-ONLY-insecure-secret":
        raise RuntimeError("Refusing to start: SECRET_KEY must be set to a strong random value in production.")


def _bootstrap_admin() -> None:
    """Create the initial admin from env vars exactly once (no public signup)."""
    with SessionLocal() as db:
        admin_count = db.scalar(select(func.count(User.id)).where(User.role == UserRole.ADMIN)) or 0
        if admin_count > 0:
            return
        username = (settings.admin_bootstrap_username or "").strip().lower()
        password = settings.admin_bootstrap_password or ""
        if not username or not password:
            logger.warning("No admin account exists. Run: python -m scripts.create_admin")
            return
        if len(password) < 8:
            logger.error("ADMIN_BOOTSTRAP_PASSWORD must be at least 8 characters; bootstrap skipped.")
            return
        db.add(
            User(
                username=username,
                full_name="Initial Administrator",
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        record_event(
            db,
            action="USER_CREATED",
            entity_type="user",
            entity_id="bootstrap",
            actor_id=None,
            actor_role="SYSTEM",
            details={"username": username, "role": "ADMIN", "via": "env_bootstrap"},
        )
        db.commit()
        logger.info("Initial admin account '%s' created via environment bootstrap.", username)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ensure_production_safety()
    # Local-dev convenience: create tables if the database is empty.
    # Production deployments should use Alembic migrations instead (see README).
    Base.metadata.create_all(bind=engine)
    _bootstrap_admin()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "QR-based return verification and AI product inspection platform. "
        "All inference results are real; no mock data is returned by these APIs."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router)
app.include_router(auth_router.router)
app.include_router(users.router)
app.include_router(catalogue.router)
app.include_router(returns.router)
app.include_router(qr_otp.returns_qr_router)
app.include_router(qr_otp.qr_router)
app.include_router(qr_otp.otp_router)
app.include_router(inspections.router)
app.include_router(review.router)
