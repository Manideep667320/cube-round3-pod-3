"""Centralized configuration settings for Prep Manager (KI Rule: Single settings instance)."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Prep Manager (Cube Round 2)"
    environment: str = "production"
    debug: bool = False

    # Tenancy defaults (Rule 1)
    default_org_id: str = "org_demo_alpha"
    allowed_orgs: list[str] = ["org_demo_alpha", "org_demo_bravo"]

    # Storage paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    storage_dir: Path = base_dir / "storage"
    fixtures_dir: Path = base_dir.parent.parent / "fixtures"

    # Multimodal VLM settings (Rule 2: Batched single-call)
    vlm_provider: str = "gemini"  # "gemini", "openai", or "mock"
    vlm_model: str = "gemini-3.5-flash"
    vlm_api_key: str = ""
    vlm_timeout_seconds: float = 2.0  # limit for warehouse packing line

    # Operational economics constraints
    max_cost_per_unit_usd: float = 0.010
    target_prep_price_min_usd: float = 0.40
    target_prep_price_max_usd: float = 1.10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
