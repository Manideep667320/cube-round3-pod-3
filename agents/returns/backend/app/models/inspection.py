"""Inspection, OCR, YOLO detection, evidence, decision and review models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agents.returns.backend.app.db.session import Base
from agents.returns.backend.app.models.enums import InspectionStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    return_id: Mapped[str] = mapped_column(String(36), ForeignKey("returns.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    otp_challenge_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("otp_challenges.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=InspectionStatus.PROCESSING, nullable=False)

    # Image metadata only; binary content lives in the controlled storage directory.
    image_stored_name: Mapped[str] = mapped_column(String(128), nullable=False)
    image_original_name: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    image_content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    image_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    image_width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    image_height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which kind of view this photo provides (see ViewType). A CONTENTS_LAYOUT
    # photo (all returned contents laid out) is the only single-image evidence
    # that can support CONFIRMED_MISSING for an expected component.
    view_type: Mapped[str] = mapped_column(String(24), default="STANDARD", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    return_record: Mapped["ReturnRecord"] = relationship(back_populates="inspections")  # noqa: F821
    ocr_result: Mapped["OCRResult | None"] = relationship(
        back_populates="inspection", cascade="all, delete-orphan", uselist=False
    )
    detection_run: Mapped["DetectionRun | None"] = relationship(
        back_populates="inspection", cascade="all, delete-orphan", uselist=False
    )
    evidence: Mapped["EvidenceRecord | None"] = relationship(
        back_populates="inspection", cascade="all, delete-orphan", uselist=False
    )
    ai_analysis: Mapped["AIAnalysis | None"] = relationship(
        back_populates="inspection", cascade="all, delete-orphan", uselist=False
    )
    decision: Mapped["Decision | None"] = relationship(
        back_populates="inspection", cascade="all, delete-orphan", uselist=False
    )


class OCRResult(Base):
    __tablename__ = "ocr_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inspections.id"), nullable=False, index=True, unique=True
    )
    engine: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    full_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mean_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..100 scale
    # [{"text": str, "confidence": float, "box": [[x,y]x4]}]
    blocks: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    processing_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    inspection: Mapped[Inspection] = relationship(back_populates="ocr_result")


class DetectionRun(Base):
    __tablename__ = "detection_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inspections.id"), nullable=False, index=True, unique=True
    )
    model_name: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    model_path: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    device: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.35, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    inference_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    inspection: Mapped[Inspection] = relationship(back_populates="detection_run")
    detections: Mapped[list["Detection"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("detection_runs.id"), nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    class_label: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # [x1, y1, x2, y2] in pixels, validated to lie within the image bounds.
    bbox: Mapped[list] = mapped_column(JSON, nullable=False)

    run: Mapped[DetectionRun] = relationship(back_populates="detections")


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inspections.id"), nullable=False, index=True, unique=True
    )
    # Structured evidence (see evidence_service.EVIDENCE_SCHEMA_VERSION):
    # identity, components, condition, ocr_summary, yolo_summary, ai_summary,
    # uncertainties
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    inspection: Mapped[Inspection] = relationship(back_populates="evidence")


class AIAnalysis(Base):
    """Persisted result of the Groq/Qwen visual-reasoning stage for one image.

    Only schema-validated model output is stored; the raw provider payload is
    not persisted.
    """

    __tablename__ = "ai_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inspections.id"), nullable=False, index=True, unique=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="groq", nullable=False)
    model: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Validated model output (enum-bounded fields only).
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    inspection: Mapped[Inspection] = relationship(back_populates="ai_analysis")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inspections.id"), nullable=False, index=True, unique=True
    )
    return_id: Mapped[str] = mapped_column(String(36), ForeignKey("returns.id"), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)  # APPROVE|REJECT|MANUAL_REVIEW
    # Recommended disposition (RESTOCK|REFURBISH|LIQUIDATE|DISPOSE) or NULL
    # when evidence does not support a confident recommendation.
    disposition: Mapped[str | None] = mapped_column(String(24), nullable=True)
    # [{"rule_id": str, "explanation": str, "outcome": str}]
    rationale: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(16), default="1.0", nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    inspection: Mapped[Inspection] = relationship(back_populates="decision")


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(String(36), ForeignKey("inspections.id"), nullable=False, index=True)
    return_id: Mapped[str] = mapped_column(String(36), ForeignKey("returns.id"), nullable=False, index=True)
    reviewer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)  # APPROVE|REJECT
    reason: Mapped[str] = mapped_column(Text, nullable=False)          # mandatory for overrides
    overrides_automated: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
