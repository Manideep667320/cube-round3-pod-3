"""Groq + Qwen multimodal visual-reasoning stage.

Sends the actual inspection photo(s) plus structured inspection context to a
Groq-hosted **image-capable** Qwen model and parses the response into a strict,
enum-bounded schema. The parsed output is EVIDENCE for the deterministic
decision engine — it can never directly approve a return.

Model capability note (verified Oct 2026 against https://console.groq.com/docs/vision):
- Default `qwen/qwen3.8-27b` accepts image + text inputs, supports JSON mode,
  max 3 images per request.
- Text-only Qwen models (e.g. qwen/qwen3-32b) are NOT valid here; the config
  validator and this module's docs say so explicitly.

Reliability behaviour:
- Missing API key / missing SDK => status UNAVAILABLE (pipeline continues,
  decision routes to human review; nothing is fabricated).
- Bounded retries with backoff for rate limits / transient server errors.
- Timeout per attempt (configurable).
- Malformed or schema-violating responses are retried once, then reported as
  MALFORMED — never partially trusted.
- The API key never leaves the server and is never logged.
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from agents.returns.backend.app.core.config import settings
from agents.returns.backend.app.services.condition_scale import get_condition_scale

logger = logging.getLogger("returnguard.groq")

MAX_IMAGES_PER_REQUEST = 3  # Groq vision limit


# --------------------------------------------------------------------------
# Strict response schema (what we accept from the model)
# --------------------------------------------------------------------------
class AIComponentFinding(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    observed: bool
    note: str = Field(default="", max_length=500)


class QwenInspectionResponse(BaseModel):
    """Validated shape of the model's JSON output. Enum-bounded by design."""

    identity: Literal["PASS", "FAIL", "UNCERTAIN"]
    identity_reasoning: str = Field(default="", max_length=1500)
    condition_grade: str
    condition_reasoning: str = Field(default="", max_length=1500)
    components: list[AIComponentFinding] = Field(default_factory=list, max_length=50)
    visible_defects: list[str] = Field(default_factory=list, max_length=30)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("condition_grade")
    @classmethod
    def _grade_in_scale(cls, v: str) -> str:
        scale = get_condition_scale()
        if v not in scale.grade_codes:
            raise ValueError(f"condition_grade '{v}' not in scale {scale.grade_codes}")
        return v

    @field_validator("identity_reasoning", "condition_reasoning")
    @classmethod
    def _strip_text(cls, v: str) -> str:
        return v.strip()


@dataclass
class AIData:
    """Pipeline-facing result of the visual-reasoning stage."""

    status: str
    provider: str = "groq"
    model: str = ""
    latency_ms: int = 0
    attempts: int = 1
    identity: str | None = None            # PASS | FAIL | UNCERTAIN
    identity_reasoning: str = ""
    condition_grade: str | None = None     # validated against the condition scale
    condition_reasoning: str = ""
    components: list[dict] = field(default_factory=list)
    visible_defects: list[str] = field(default_factory=list)
    confidence: float | None = None
    error: str | None = None
    payload: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Availability / configuration
# --------------------------------------------------------------------------
def get_groq_info() -> dict:
    """Cheap health report. Never exposes the key itself."""
    try:
        import groq  # noqa: F401

        sdk_installed = True
    except ImportError:
        sdk_installed = False
    key_present = bool(settings.groq_api_key.strip())
    return {
        "provider": "groq",
        "model": settings.groq_vision_model,
        "sdk_installed": sdk_installed,
        "key_present": key_present,
        "enabled": sdk_installed and key_present,
        "vision_model_expected": True,
    }


def _client():
    from groq import Groq

    return Groq(
        api_key=settings.groq_api_key.strip(),
        timeout=settings.groq_timeout_seconds,
        max_retries=0,  # we implement our own bounded retry policy
    )


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a returns-inspection analyst. You will receive photographs of a
returned product together with the expected order data, OCR text and object-detection
results. Answer ONLY with a JSON object of exactly this shape:
{
  "identity": "PASS" | "FAIL" | "UNCERTAIN",
  "identity_reasoning": "<short explanation citing what you actually see>",
  "condition_grade": "<one of the allowed grade codes>",
  "condition_reasoning": "<short explanation of visible wear/damage>",
  "components": [{"name": "<expected component name>", "observed": true|false, "note": "<short>"}],
  "visible_defects": ["<short defect descriptions visible in the photos>"],
  "confidence": 0.0..1.0
}
Rules:
- Report ONLY what is actually visible in the photographs. Never invent text, labels or objects.
- If the label/model number is unreadable or ambiguous, use "UNCERTAIN" for identity.
- Mark a component observed only when you can see it in the photos.
- Use only the allowed condition grade codes provided in the context.
- confidence reflects your overall certainty in the identity+condition assessment."""


def _build_context(
    return_record,
    ocr_texts: list[str],
    detections: list[dict],
    view_types: list[str],
) -> str:
    scale = get_condition_scale()
    components = [
        {"name": c.name, "yolo_hints": [h for h in (c.yolo_class_hints or "").split(",") if h]}
        for c in return_record.expected_components
    ]
    context = {
        "expected_order": {
            "sku": return_record.expected_sku,
            "product_description": return_record.product_description,
            "expected_components": components,
        },
        "local_ocr_text": "\n".join(t for t in ocr_texts if t)[:3000],
        "local_yolo_detections": detections[:50],
        "photo_view_types": view_types,
        "allowed_condition_grades": [
            {"code": g["code"], "definition": g["definition"]} for g in scale.grades
        ],
    }
    return json.dumps(context, ensure_ascii=False)


def _encode_image(path: Path) -> str | None:
    mime, _ = mimetypes.guess_type(str(path))
    if not mime or not mime.startswith("image/"):
        mime = "image/jpeg"
    try:
        data = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return None
    return f"data:{mime};base64,{data}"


# --------------------------------------------------------------------------
# The call itself
# --------------------------------------------------------------------------
def run_ai_analysis(return_record, image_paths: list[Path], ocr_texts: list[str],
                    detections: list[dict], view_types: list[str]) -> AIData:
    """Run the Groq/Qwen visual-reasoning stage. Never raises into the pipeline."""
    info = get_groq_info()
    model = settings.groq_vision_model
    if not info["enabled"]:
        reason = "GROQ_API_KEY is not configured" if info["sdk_installed"] else "the 'groq' SDK is not installed"
        return AIData(status="UNAVAILABLE", model=model,
                      error=f"AI visual reasoning disabled: {reason}. Pipeline continues without AI evidence.")

    encoded = [u for p in image_paths[:MAX_IMAGES_PER_REQUEST] if (u := _encode_image(p))]
    if not encoded:
        return AIData(status="FAILED", model=model, error="No readable image data for the AI stage.")

    context_json = _build_context(return_record, ocr_texts, detections, view_types)
    content: list[dict] = [{"type": "text", "text": f"Inspection context:\n{context_json}"}]
    for url in encoded:
        content.append({"type": "image_url", "image_url": {"url": url}})

    started = time.perf_counter()
    last_error = "unknown"
    corrective: str | None = None
    max_attempts = 1 + max(0, settings.groq_max_retries)
    validation_attempts = 0

    for attempt in range(1, max_attempts + 1):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content + ([{"type": "text", "text": corrective}] if corrective else [])},
        ]
        try:
            client = _client()
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                max_completion_tokens=1500,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # noqa: BLE001 - classify below, never crash the pipeline
            name = type(exc).__name__
            status = _classify_exception(exc)
            last_error = f"{name}: {str(exc)[:200]}"
            retryable = status in ("retryable", "rate_limited", "timeout")
            if retryable and attempt < max_attempts:
                time.sleep(min(2.0 * attempt, 6.0))  # bounded backoff
                continue
            final = "TIMEOUT" if status == "timeout" else ("RATE_LIMITED" if status == "rate_limited" else "FAILED")
            logger.warning("Groq call failed (status=%s attempt=%d): %s", final, attempt, name)
            return AIData(status=final, model=model, attempts=attempt,
                          latency_ms=int((time.perf_counter() - started) * 1000), error=last_error)

        raw = (completion.choices[0].message.content or "") if completion.choices else ""
        try:
            parsed = json.loads(raw)
            validated = QwenInspectionResponse.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            validation_attempts += 1
            last_error = f"malformed model response: {type(exc).__name__}"
            if validation_attempts < 2:
                corrective = ("Your previous reply did not match the required JSON schema. "
                              "Reply again with ONLY the valid JSON object, using exactly the allowed values.")
                continue
            return AIData(status="MALFORMED", model=model, attempts=attempt,
                          latency_ms=int((time.perf_counter() - started) * 1000), error=last_error)

        known = {c.name.strip().lower() for c in return_record.expected_components}
        components = [
            {"name": c.name, "observed": c.observed, "note": c.note}
            for c in validated.components if c.name.strip().lower() in known
        ]
        payload = validated.model_dump()
        return AIData(
            status="OK", model=model, attempts=attempt,
            latency_ms=int((time.perf_counter() - started) * 1000),
            identity=validated.identity,
            identity_reasoning=validated.identity_reasoning,
            condition_grade=validated.condition_grade,
            condition_reasoning=validated.condition_reasoning,
            components=components,
            visible_defects=[d[:200] for d in validated.visible_defects],
            confidence=validated.confidence,
            payload=payload,
        )

    if validation_attempts:
        return AIData(status="MALFORMED", model=model, attempts=max_attempts,
                      latency_ms=int((time.perf_counter() - started) * 1000), error=last_error)

    return AIData(status="FAILED", model=model, attempts=max_attempts,
                  latency_ms=int((time.perf_counter() - started) * 1000), error=last_error)


def _classify_exception(exc: Exception) -> str:
    """Map provider exceptions to retry policy categories."""
    name = type(exc).__name__
    msg = str(exc).lower()
    if "timed out" in msg or "timeout" in name.lower():
        return "timeout"
    if "429" in msg or "rate limit" in msg or "RateLimit" in name:
        return "rate_limited"
    if "400" in msg and "image" in msg:
        return "fatal"  # e.g. unsupported image — do not retry
    if name in {"APIConnectionError", "InternalServerError", "APITimeoutError"} or "5" == str(getattr(exc, "status_code", ""))[:1]:
        return "retryable"
    if "RateLimit" in name or "InternalServer" in name:
        return "retryable"
    return "fatal"
