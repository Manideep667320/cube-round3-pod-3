"""Opt-in LIVE Groq/Qwen inference test.

Runs only when BOTH conditions hold:
  - a real GROQ_API_KEY is configured, and
  - RUN_LIVE_GROQ=1 is set in the environment.

Otherwise it reports the blocker explicitly instead of fabricating a result.
"""
from __future__ import annotations

import io
import os

import pytest

from agents.returns.backend.tests.conftest import _ORIGINAL_GROQ_KEY

pytestmark = pytest.mark.groq_live


def _synthetic_product_image() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 150, 700, 500], fill=(35, 35, 40))
    draw.rectangle([130, 180, 670, 400], fill=(70, 130, 180))
    draw.text((150, 430), "SKU: DEMO-1234", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_live_groq_vision_returns_validated_structure(tmp_path, monkeypatch):
    from agents.returns.backend.app.core.config import settings
    from agents.returns.backend.app.models import ExpectedComponent, ReturnRecord
    from agents.returns.backend.app.services import groq_service

    if os.environ.get("RUN_LIVE_GROQ") != "1":
        pytest.skip("BLOCKED: set RUN_LIVE_GROQ=1 to enable live Groq tests.")
    if not _ORIGINAL_GROQ_KEY:
        pytest.skip("BLOCKED: GROQ_API_KEY is not configured; live Groq inference cannot be tested.")
    # Re-enable the pristine key for this live call only.
    monkeypatch.setattr(settings, "groq_api_key", _ORIGINAL_GROQ_KEY)
    monkeypatch.setattr(settings, "groq_timeout_seconds", 60.0)

    img = tmp_path / "live.jpg"
    img.write_bytes(_synthetic_product_image())

    ret = ReturnRecord(return_code="RG-LIVE", order_reference="o",
                       expected_sku="DEMO-1234", product_description="Blue electronic device",
                       created_by_id="x")
    ret.expected_components = [
        ExpectedComponent(name="device", yolo_class_hints="laptop"),
        ExpectedComponent(name="cable", yolo_class_hints="usb cable"),
    ]

    result = groq_service.run_ai_analysis(
        ret, [img], ["SKU: DEMO-1234"], [{"label": "laptop", "confidence": 0.8, "bbox": [1, 1, 50, 50]}],
        ["STANDARD"],
    )
    # The model must produce a schema-validated structure or an honest failure.
    assert result.status in ("OK", "RATE_LIMITED", "TIMEOUT", "MALFORMED", "FAILED"), result.status
    if result.status == "OK":
        assert result.identity in ("PASS", "FAIL", "UNCERTAIN")
        assert result.condition_grade in get_scale_codes()
        assert result.confidence is None or 0.0 <= result.confidence <= 1.0
        assert result.payload, "validated payload must be stored"
    else:
        pytest.fail(f"Live Groq call did not succeed (status={result.status}): {result.error}")


def get_scale_codes() -> tuple[str, ...]:
    from agents.returns.backend.app.services.condition_scale import get_condition_scale

    return get_condition_scale().grade_codes
