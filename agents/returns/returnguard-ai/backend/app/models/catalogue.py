"""Product catalogue: admin-managed definitions of sellable products.

A return may reference a catalogue entry; the expected component list and
product metadata used by the inspection pipeline come from here (or from the
return's own fields when no catalogue entry is linked).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CatalogueProduct(Base):
    __tablename__ = "catalogue_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # [{"name": str, "yolo_class_hints": [str], "ocr_text_hint": str}]
    default_components: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Key identifiers used to corroborate identity (brand, model family, colour).
    identifying_features: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_by_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
