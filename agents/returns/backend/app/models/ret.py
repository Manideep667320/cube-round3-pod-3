"""Return record and expected component models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agents.returns.backend.app.db.session import Base
from agents.returns.backend.app.models.enums import ReturnStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class ReturnRecord(Base):
    __tablename__ = "returns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    return_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    order_reference: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    expected_sku: Mapped[str] = mapped_column(String(64), nullable=False)
    # Optional link to the admin-managed product catalogue.
    catalogue_product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("catalogue_products.id"), nullable=True, index=True
    )
    product_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    assigned_agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default=ReturnStatus.PENDING, nullable=False, index=True)
    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    expected_components: Mapped[list["ExpectedComponent"]] = relationship(
        back_populates="return_record", cascade="all, delete-orphan", lazy="selectin"
    )
    qr_authorizations: Mapped[list["QRAuthorization"]] = relationship(  # noqa: F821
        back_populates="return_record", cascade="all, delete-orphan"
    )
    inspections: Mapped[list["Inspection"]] = relationship(  # noqa: F821
        back_populates="return_record", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Return {self.return_code} status={self.status}>"


class ExpectedComponent(Base):
    __tablename__ = "expected_components"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    return_id: Mapped[str] = mapped_column(String(36), ForeignKey("returns.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # Optional hint: detection class names that count as evidence for this component
    # (e.g. {"laptop", "computer"}). Used by the evidence builder / decision engine.
    yolo_class_hints: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    ocr_text_hint: Mapped[str] = mapped_column(String(128), default="", nullable=False)

    return_record: Mapped[ReturnRecord] = relationship(back_populates="expected_components")
