"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(ORMModel):
    id: str
    username: str
    full_name: str
    role: str
    phone: str | None = None
    phone_verified: bool
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(pattern=r"^(ADMIN|AGENT|OPERATOR)$")
    full_name: str = Field(default="", max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    phone_verified: bool = False


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    phone_verified: bool | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


# --------------------------------------------------------------------------
# Returns
# --------------------------------------------------------------------------
class ExpectedComponentIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    yolo_class_hints: list[str] = Field(default_factory=list)
    ocr_text_hint: str = Field(default="", max_length=128)


class ExpectedComponentOut(ORMModel):
    id: str
    name: str
    yolo_class_hints: str
    ocr_text_hint: str


class ReturnCreateRequest(BaseModel):
    order_reference: str = Field(min_length=1, max_length=64)
    expected_sku: str = Field(min_length=1, max_length=64)
    product_description: str = Field(default="", max_length=2000)
    expected_components: list[ExpectedComponentIn] = Field(default_factory=list)
    assigned_agent_id: str | None = None
    # Optional link to the admin-managed product catalogue; when set and no
    # components are supplied, the catalogue defaults are used.
    catalogue_product_id: str | None = None


class ReturnUpdateRequest(BaseModel):
    product_description: str | None = Field(default=None, max_length=2000)
    assigned_agent_id: str | None = None
    expected_components: list[ExpectedComponentIn] | None = None


class QRAuthOut(ORMModel):
    id: str
    return_id: str
    token_prefix: str
    status: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None


class CatalogueProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    default_components: list[ExpectedComponentIn] = Field(default_factory=list)
    identifying_features: list[str] = Field(default_factory=list, max_length=30)


class CatalogueProductOut(ORMModel):
    id: str
    sku: str
    name: str
    description: str
    default_components: list
    identifying_features: list
    created_by_id: str
    created_at: datetime


class AIAnalysisOut(ORMModel):
    id: str
    provider: str
    model: str
    status: str
    latency_ms: int
    attempts: int
    payload: dict
    error: str | None = None


class ReturnOut(ORMModel):
    id: str
    return_code: str
    order_reference: str
    expected_sku: str
    catalogue_product_id: str | None = None
    product_description: str
    status: str
    assigned_agent_id: str | None = None
    created_by_id: str
    created_at: datetime
    updated_at: datetime
    expected_components: list[ExpectedComponentOut] = Field(default_factory=list)


class ReturnDetailOut(ReturnOut):
    qr_authorizations: list[QRAuthOut] = Field(default_factory=list)
    otp_summary: list["OTPChallengeSummary"] = Field(default_factory=list)
    inspections: list["InspectionSummary"] = Field(default_factory=list)


class OTPChallengeSummary(BaseModel):
    id: str
    status: str
    attempts: int
    issued_at: datetime
    expires_at: datetime
    verified_at: datetime | None = None


# --------------------------------------------------------------------------
# QR
# --------------------------------------------------------------------------
class QRGenerateResponse(BaseModel):
    qr_authorization: QRAuthOut
    # Raw token, shown exactly once so the admin can print/encode the QR.
    token: str
    qr_png_base64: str
    scan_value: str  # value encoded inside the QR image


class QRScanRequest(BaseModel):
    token: str = Field(min_length=8, max_length=512)


class QRScanResponse(BaseModel):
    scan_token: str
    return_id: str
    return_code: str
    product_description: str
    assigned_agent_id: str


# --------------------------------------------------------------------------
# OTP
# --------------------------------------------------------------------------
class OTPRequestOut(BaseModel):
    """Response after requesting an OTP. Never contains the code."""

    masked_phone: str
    expires_at: datetime
    resend_available_at: datetime
    max_attempts: int


class OTPVerifyRequest(BaseModel):
    scan_token: str
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class OTPVerifyResponse(BaseModel):
    inspection_token: str
    return_id: str
    return_code: str


# --------------------------------------------------------------------------
# Inspections
# --------------------------------------------------------------------------
class OCRBlock(BaseModel):
    text: str
    confidence: float | None = None
    box: list[list[float]] | None = None


class OCRResultOut(ORMModel):
    id: str
    engine: str
    engine_version: str
    status: str
    full_text: str
    mean_confidence: float | None = None
    blocks: list[Any] = Field(default_factory=list)
    processing_ms: int
    error: str | None = None


class DetectionOut(ORMModel):
    class_id: int
    class_label: str
    confidence: float
    bbox: list[float]


class DetectionRunOut(ORMModel):
    id: str
    model_name: str
    device: str
    confidence_threshold: float
    status: str
    inference_ms: int
    error: str | None = None
    detections: list[DetectionOut] = Field(default_factory=list)


class EvidenceOut(ORMModel):
    id: str
    payload: dict[str, Any]


class DecisionOut(ORMModel):
    id: str
    outcome: str
    disposition: str | None = None
    rationale: list[Any]
    engine_version: str
    decided_at: datetime


class ReviewOut(ORMModel):
    id: str
    inspection_id: str
    return_id: str
    reviewer_id: str
    outcome: str
    reason: str
    overrides_automated: bool
    created_at: datetime


class InspectionSummary(BaseModel):
    id: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    decision_outcome: str | None = None
    image_url: str | None = None


class InspectionDetailOut(BaseModel):
    id: str
    return_id: str
    return_code: str
    agent_id: str
    status: str
    view_type: str = "STANDARD"
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    image: dict[str, Any]
    ocr: OCRResultOut | None = None
    detection_run: DetectionRunOut | None = None
    ai_analysis: AIAnalysisOut | None = None
    evidence: EvidenceOut | None = None
    decision: DecisionOut | None = None
    reviews: list[ReviewOut] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Review / audit / stats
# --------------------------------------------------------------------------
class ReviewResolveRequest(BaseModel):
    outcome: str = Field(pattern=r"^(APPROVE|REJECT)$")
    reason: str = Field(min_length=5, max_length=2000)


class AuditEventOut(ORMModel):
    id: str
    actor_id: str | None = None
    actor_role: str | None = None
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any]
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    app_env: str
    database: dict[str, Any]
    sms_provider: str
    ocr: dict[str, Any]
    yolo: dict[str, Any]
    storage: dict[str, Any]
    groq: dict[str, Any]
    condition_scale: dict[str, Any]


class StatsOut(BaseModel):
    returns_by_status: dict[str, int]
    total_returns: int
    total_inspections: int
    decisions: dict[str, int]
    otp_challenges: dict[str, int]
    agents: int
