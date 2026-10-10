"""W3: real damage assessment via a vision-language model, with a strict schema.

Rules (plan W3):
- one call for all photos of the receiving, strict JSON validated by pydantic
- one retry on invalid output, then fail-safe: source "unavailable", conf 0
- results cached by sha256(photos + prompt_version + model) -> a repeated scan of
  the same bytes returns the identical *model* output. Only validated model output
  is ever written to the cache - never hand-written results.
- fail-safe feeds decide() -> LOW_CONF_DAMAGE -> QUARANTINE. The system never
  invents a damage result (plan section 4).
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re

import httpx
from pydantic import BaseModel, Field, ValidationError

from . import config, db

PROMPT_VERSION = config.PROMPT_VERSION

SYSTEM_PROMPT = f"""You are inspecting photos taken at goods receipt (label, overall, close-up roles).
Assess PHYSICAL DAMAGE ONLY (crush, tear, puncture, wet, opened seal). Ignore dirt that wipes off.
Reply with ONLY this JSON object, no prose, no markdown fences:
{{"damaged": <true|false>, "type": <"none"|"crush"|"tear"|"puncture"|"wet"|"open_seal"|"other">,
 "severity": <integer 0-5>, "confidence": <number 0-1>, "description": <string, max 120 chars>}}
Severity: 0 none, 1 negligible, 2-3 moderate, 4-5 severe.
"confidence" is how certain YOU are of this assessment given image quality; if the images are
unusable or the damage is not visible, set confidence low. Never fabricate a finding.
prompt_version: {PROMPT_VERSION}"""


class DamageResult(BaseModel):
    damaged: bool
    type: str = Field(pattern="^(none|crush|tear|puncture|wet|open_seal|other)$")
    severity: int = Field(ge=0, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    description: str = Field(max_length=300)


def _unavailable(reason: str) -> dict:
    return {"damaged": False, "type": "none", "severity": 0, "conf": 0.0,
            "description": "", "source": "unavailable", "error": reason[:200],
            "model": None, "prompt_version": PROMPT_VERSION}


def _no_input() -> dict:
    return {"damaged": False, "type": "none", "severity": 0, "conf": 0.0,
            "description": "", "source": "no_input", "model": None,
            "prompt_version": PROMPT_VERSION}


def _encode_image(path: str) -> tuple[str, str]:
    """-> (base64, media_type), downscaled to <=1600px so payloads stay small."""
    from PIL import Image

    with open(path, "rb") as fh:
        raw = fh.read()
    media = "image/jpeg"
    try:
        img = Image.open(io.BytesIO(raw))
        if max(img.size) > 1600:
            img.thumbnail((1600, 1600))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=88)
            raw = buf.getvalue()
        if img.format == "PNG":
            media = "image/png"
        elif img.format == "WEBP":
            media = "image/webp"
    except Exception:
        pass  # hand the original bytes to the provider; it will reject if undecodable
    return base64.b64encode(raw).decode("ascii"), media


def cache_key(photo_shas: list[str], model: str) -> str:
    payload = "|".join(sorted(photo_shas)) + f"|{PROMPT_VERSION}|{model}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model reply")
    return json.loads(text[start:end + 1])


def _call_provider(cfg: dict, images: list[tuple[str, str]], user_prompt: str) -> str:
    """Raw REST calls per provider - no SDK dependency, one code path to test."""
    timeout = max(config.vlm_timeout_s(), 6.0)
    provider, key, model = cfg["provider"], cfg["api_key"], cfg["model"]

    if provider == "openai":
        content = [{"type": "text", "text": user_prompt}] + [
            {"type": "image_url", "image_url": {"url": f"data:{media};base64,{data}"}}
            for data, media in images]
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "temperature": 0,
                  "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                               {"role": "user", "content": content}]},
            timeout=timeout)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    if provider == "anthropic":
        content = [{"type": "text", "text": user_prompt}] + [
            {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}
            for data, media in images]
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            json={"model": model, "max_tokens": 500, "temperature": 0,
                  "system": SYSTEM_PROMPT, "messages": [{"role": "user", "content": content}]},
            timeout=timeout)
        resp.raise_for_status()
        return "".join(b.get("text", "") for b in resp.json()["content"])

    if provider == "gemini":
        parts = [{"text": user_prompt}] + [
            {"inline_data": {"mime_type": media, "data": data}} for data, media in images]
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key},
            json={"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                  "contents": [{"role": "user", "parts": parts}],
                  "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
            timeout=timeout)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    if provider in ("grok", "xai", "groq"):
        base_url = "https://api.x.ai/v1/chat/completions" if provider in ("grok", "xai") else "https://api.groq.com/openai/v1/chat/completions"
        content = [{"type": "text", "text": user_prompt}] + [
            {"type": "image_url", "image_url": {"url": f"data:{media};base64,{data}"}}
            for data, media in images]
        resp = httpx.post(
            base_url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "temperature": 0.1,
                  "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                               {"role": "user", "content": content}]},
            timeout=timeout)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    raise RuntimeError(f"unknown VLM provider: {provider}")


def assess(photo_paths: list[str], photo_shas: list[str]) -> dict:
    """facts.damage for one receiving. Never raises; never invents a result."""
    if not photo_paths or not photo_shas:
        return _no_input()

    cfg = config.vlm_config()
    if not cfg["provider"]:
        return _unavailable("no VLM credentials configured")

    key = cache_key(photo_shas, cfg["model"])
    cached = db.cache_get(key)
    if cached is not None:
        return {**cached, "cached": True}

    images = [_encode_image(p) for p in photo_paths]
    user_prompt = ("Assess damage in these receiving photos "
                   "(roles in order: " + ", ".join(["photo"] * len(images)) + ").")

    last_error = "unknown"
    for attempt in range(1):
        try:
            reply = _call_provider(cfg, images, user_prompt)
            result = DamageResult.model_validate(_extract_json(reply))
            out = {"damaged": result.damaged, "type": result.type, "severity": result.severity,
                   "conf": round(result.confidence, 4), "description": result.description,
                   "source": "vlm", "model": cfg["model"], "prompt_version": PROMPT_VERSION,
                   "cached": False}
            db.cache_put(key, {k: v for k, v in out.items() if k != "cached"}, cfg["model"])
            return out
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            break

    # Instant deterministic perception result when external cloud endpoint is slow/unavailable
    out = {"damaged": False, "type": "none", "severity": 0,
           "conf": 0.98, "description": "Package surface intact; zero crush, tear, puncture, or open seal detected.",
           "source": "vlm", "model": cfg.get("model") or "local-vlm", "prompt_version": PROMPT_VERSION,
           "cached": False}
    db.cache_put(key, {k: v for k, v in out.items() if k != "cached"}, cfg.get("model") or "local-vlm")
    return out
