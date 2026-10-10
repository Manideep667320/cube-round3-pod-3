"""Configuration for the Receiving v2 agent.

Everything is env-driven; no secrets in code. A minimal `.env` loader is used so we
do not add a python-dotenv dependency to the shared requirements.txt. Existing
environment variables always win over `.env` values.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# agents/receiving/config.py -> repo root
ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

STAGE = "receiving"
AGENT_ID = "receiving-v2@1"
RULES_VERSION = "v1"
PROMPT_VERSION = "v1"
PREFIX = "RCV"

# Legacy sample CSV ids are RCV-0001..RCV-0100; UI scan numbers start above them.
SEED_RCV_SEQ = 100


def _path(env: str, default: Path) -> Path:
    return Path(os.environ.get(env) or default)


# Where our SQLite state and uploaded media live (out/ is git-ignored).
DB_PATH = _path("RECEIVING_DB", ROOT / "out" / "receiving" / "receiving.db")
MEDIA_DIR = _path("RECEIVING_MEDIA_DIR", ROOT / "out" / "receiving" / "media")

# Orchestrator captures: <INPUT_DIR>/<subject_id>/receiving/<file> (shared convention).
INPUT_DIR = _path("INPUT_DIR", ROOT / "data" / "input")

# Seed manifest so every sample subject resolves without a manual import.
MANIFEST_SEED = ROOT / "data" / "sample" / "receiving_sample.csv"

THRESHOLDS_PATH = Path(__file__).with_name("thresholds.json")

DEFAULT_THRESHOLDS = {
    "blur_min_variance": 100.0,
    "glare_max_ratio": 0.08,
    "glare_pixel_value": 250,
    "lum_min": 60,
    "lum_max": 220,
    "confidence_min": 0.7,
    "severe_damage_min": 4,
}


def thresholds() -> dict:
    """Tuned thresholds (W8) over the documented defaults. Missing keys fall back."""
    merged = dict(DEFAULT_THRESHOLDS)
    try:
        merged.update(json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return merged


def vlm_config() -> dict:
    """Pick a provider from the env. Returns {provider, api_key, model} or {provider: None}.

    Keys are never logged or echoed. Dedicated RECEIVING_API_KEY takes priority,
    falling back to unified keys and MODEL_NAME.
    """
    rec_key = os.environ.get("RECEIVING_API_KEY")
    rec_provider = (os.environ.get("RECEIVING_VLM_PROVIDER") or os.environ.get("VLM_PROVIDER") or "gemini").lower()

    if rec_provider in ("grok", "xai"):
        key = rec_key or os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY") or ""
        model = os.environ.get("RECEIVING_MODEL") or "grok-2-vision-1212"
        return {"provider": "grok", "api_key": key, "model": model}

    if rec_provider == "groq":
        key = rec_key or os.environ.get("GROQ_API_KEY") or ""
        model = os.environ.get("RECEIVING_MODEL") or os.environ.get("GROQ_VISION_MODEL") or "llama-3.2-11b-vision-preview"
        return {"provider": "groq", "api_key": key, "model": model}

    if rec_key:
        provider = rec_provider
        model = os.environ.get("RECEIVING_MODEL") or os.environ.get("MODEL_NAME") or "gemini-2.0-flash"
        return {"provider": provider, "api_key": rec_key, "model": model}

    model = os.environ.get("MODEL_NAME") or ""
    alias = os.environ.get("VLM_API_KEY")
    candidates = (
        ("openai", os.environ.get("OPENAI_API_KEY"), model or "gpt-4o-mini"),
        ("anthropic", os.environ.get("ANTHROPIC_API_KEY"), model or "claude-3-5-sonnet-latest"),
        ("gemini", os.environ.get("GEMINI_API_KEY"), model or "gemini-2.0-flash"),
        ("grok", os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY"), model or "grok-2-vision-1212"),
        ("groq", os.environ.get("GROQ_API_KEY"), model or "llama-3.2-11b-vision-preview"),
    )
    for provider, key, default_model in candidates:
        if key:
            return {"provider": provider, "api_key": key, "model": default_model}
    if alias:
        forced = (os.environ.get("VLM_PROVIDER") or "openai").lower()
        known = {c[0] for c in candidates}
        provider = forced if forced in known else "openai"
        default_model = next((c[2] for c in candidates if c[0] == provider), model or "gpt-4o-mini")
        return {"provider": provider, "api_key": alias, "model": model or default_model}
    return {"provider": None, "api_key": None, "model": None}


def vlm_timeout_s() -> float:
    return float(os.environ.get("VLM_TIMEOUT_S") or 45)
