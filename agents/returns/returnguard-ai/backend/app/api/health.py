"""Health endpoint reporting real dependency availability (no secrets)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas import HealthOut
from app.services.ocr_service import get_engine_info
from app.services.condition_scale import get_condition_scale
from app.services.groq_service import get_groq_info
from app.services.sms_service import get_sms_provider
from app.services.yolo_service import get_model_info

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthOut)
def health(db: Session = Depends(get_db)):
    # Database: real connectivity check.
    try:
        db.execute(text("SELECT 1"))
        database = {"status": "ok", "url_scheme": settings.database_url.split("://", 1)[0]}
    except Exception:
        database = {"status": "error", "url_scheme": settings.database_url.split("://", 1)[0]}

    ocr = get_engine_info()
    yolo = get_model_info()

    storage_dir = Path(settings.storage_dir)
    try:
        storage_dir.mkdir(parents=True, exist_ok=True)
        probe = storage_dir / ".healthprobe"
        probe.write_text("ok")
        probe.unlink()
        storage = {"status": "ok", "writable": True}
    except OSError:
        storage = {"status": "error", "writable": False}

    provider = get_sms_provider()
    scale = get_condition_scale()
    overall = "ok" if database["status"] == "ok" and storage["status"] == "ok" else "degraded"
    return HealthOut(
        status=overall,
        app_env=settings.app_env,
        database=database,
        sms_provider=provider.name,
        ocr=ocr,
        yolo=yolo,
        storage=storage,
        groq=get_groq_info(),
        condition_scale={"name": scale.name, "source": scale.source, "policy_version": scale.policy_version},
    )
