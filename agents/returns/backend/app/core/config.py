"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    app_name: str = "ReturnGuard AI"
    app_env: str = Field(default="development", description="development | test | production")
    secret_key: str = Field(default="CHANGE-ME-DEV-ONLY-insecure-secret", min_length=8)
    access_token_expire_minutes: int = 480
    inspection_token_expire_minutes: int = 30
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Database ---
    database_url: str = "sqlite:///./data/returnguard.db"

    # --- Storage ---
    storage_dir: Path = PROJECT_DIR / "storage" / "uploads"
    max_upload_mb: int = 10
    allowed_image_formats: str = "JPEG,PNG,WEBP,BMP"
    upload_hostname: str = "localhost:8000"  # used only to build absolute media URLs

    # --- QR authorizations ---
    qr_token_ttl_hours: int = 72

    # --- OTP ---
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60
    otp_max_issues_per_hour: int = 5

    # --- SMS ---
    sms_provider: str = Field(default="mock", description="mock | twilio")
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    # Local-development convenience ONLY (mock provider): when set to a file
    # path, the mock provider mirrors captured messages there so a developer
    # can read OTP codes during manual UI testing. Meaningless in production
    # because the mock provider is refused at startup there.
    mock_sms_outbox: str = ""

    # --- Groq + Qwen multimodal inspection (visual reasoning stage) ---
    # GROQ_VISION_MODEL must accept IMAGE inputs. Verified image-capable on
    # Groq (Oct 2026): qwen/qwen3.8-27b. Text-only Qwen models are not valid here.
    groq_api_key: str = Field(default="", description="Groq API key; empty disables the AI stage")
    groq_vision_model: str = "qwen/qwen3.8-27b"
    groq_timeout_seconds: float = 45.0
    groq_max_retries: int = Field(default=2, ge=0, le=5)

    # --- Condition scale (official challenge resources, when supplied) ---
    # Path to a JSON file overriding the built-in UNOFFICIAL placeholder scale.
    condition_scale_file: str = ""

    # --- OCR ---
    ocr_engine: str = Field(default="auto", description="auto | rapidocr | tesseract | none")
    ocr_timeout_seconds: float = 30.0
    ocr_low_confidence_threshold: float = Field(default=55.0, description="0-100 scale; below this mean confidence OCR is LOW_CONFIDENCE")

    # --- YOLO ---
    yolo_model_path: str = "yolov8n.pt"
    yolo_confidence_threshold: float = 0.35
    yolo_device: str = "auto"
    yolo_timeout_seconds: float = 60.0

    # --- Rate limiting ---
    login_rate_limit_attempts: int = 10
    login_rate_limit_window_seconds: int = 300
    otp_rate_limit_attempts: int = 10
    otp_rate_limit_window_seconds: int = 300

    # --- Bootstrap admin (used once when no admin exists) ---
    admin_bootstrap_username: str = ""
    admin_bootstrap_password: str = ""

    # ------------------------------------------------------------------
    @field_validator("app_env")
    @classmethod
    def _check_env(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be one of development|test|production")
        return v

    @field_validator("sms_provider")
    @classmethod
    def _check_sms(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in {"mock", "twilio"}:
            raise ValueError("SMS_PROVIDER must be 'mock' or 'twilio'")
        return v

    @field_validator("ocr_engine")
    @classmethod
    def _check_ocr(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in {"auto", "rapidocr", "tesseract", "none"}:
            raise ValueError("OCR_ENGINE must be one of auto|rapidocr|tesseract|none")
        return v

    @field_validator("yolo_confidence_threshold")
    @classmethod
    def _check_yolo_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("YOLO_CONFIDENCE_THRESHOLD must be within [0, 1]")
        return v

    @field_validator("ocr_low_confidence_threshold")
    @classmethod
    def _check_ocr_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 100.0:
            raise ValueError("OCR_LOW_CONFIDENCE_THRESHOLD must be within [0, 100]")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_formats_set(self) -> set[str]:
        return {f.strip().upper() for f in self.allowed_image_formats.split(",") if f.strip()}

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
