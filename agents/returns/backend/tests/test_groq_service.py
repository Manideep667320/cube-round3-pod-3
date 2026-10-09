"""Groq/Qwen service tests with a mocked provider.

No network access: the Groq client is faked. Live behaviour is covered by
tests/test_live_groq.py (opt-in, requires a real key).
"""
from __future__ import annotations

import json

import pytest

from agents.returns.backend.app.models import ExpectedComponent, ReturnRecord
from agents.returns.backend.app.services import groq_service
from agents.returns.backend.app.services.groq_service import AIData, QwenInspectionResponse


def _ret() -> ReturnRecord:
    ret = ReturnRecord(return_code="RG-GROQ", order_reference="o", expected_sku="SKU-1", created_by_id="x")
    ret.expected_components = [ExpectedComponent(name="charger", yolo_class_hints="charger")]
    return ret


def _fake_completion(text: str):
    class Msg:
        content = text

    class Choice:
        message = Msg()

    class Completion:
        choices = [Choice()]

    return Completion()


def _patch_client(monkeypatch, create):
    class FakeGroqModule:
        Groq = staticmethod(lambda **kwargs: type("C", (), {"chat": type("Ch", (), {"completions": type("Co", (), {"create": staticmethod(create)})()})()})())

    import sys

    monkeypatch.setitem(sys.modules, "groq", FakeGroqModule)


def test_missing_key_reports_unavailable(monkeypatch):
    from agents.returns.backend.app.core.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "")
    result = groq_service.run_ai_analysis(_ret(), [__file__], [""], [], ["STANDARD"])
    assert result.status == "UNAVAILABLE"
    assert "GROQ_API_KEY" in (result.error or "")
    assert result.identity is None and result.condition_grade is None


def test_health_info_never_exposes_key(monkeypatch):
    from agents.returns.backend.app.core.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "gsk_super_secret_value")
    info = groq_service.get_groq_info()
    assert info["key_present"] is True and info["enabled"] is True
    assert "gsk_" not in json.dumps(info)


def test_successful_response_is_validated(monkeypatch, tmp_path):
    from agents.returns.backend.app.core.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    payload = {
        "identity": "PASS", "identity_reasoning": "label matches",
        "condition_grade": "A_NEW", "condition_reasoning": "pristine",
        "components": [{"name": "charger", "observed": True, "note": "visible"}],
        "visible_defects": [], "confidence": 0.9,
    }
    _patch_client(monkeypatch, lambda **kw: _fake_completion(json.dumps(payload)))
    result = groq_service.run_ai_analysis(_ret(), [img], ["MODEL: SKU-1"], [], ["STANDARD"])
    assert result.status == "OK"
    assert result.identity == "PASS"
    assert result.condition_grade == "A_NEW"
    assert result.components[0]["name"] == "charger" and result.components[0]["observed"] is True
    assert result.confidence == 0.9


def test_unknown_component_names_are_filtered(monkeypatch, tmp_path):
    from agents.returns.backend.app.core.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    img = tmp_path / "p.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0x")
    payload = {
        "identity": "UNCERTAIN", "identity_reasoning": "", "condition_grade": "UNKNOWN",
        "condition_reasoning": "", "confidence": 0.4,
        "components": [
            {"name": "charger", "observed": True, "note": ""},
            {"name": "totally invented part", "observed": True, "note": ""},
        ],
        "visible_defects": [],
    }
    _patch_client(monkeypatch, lambda **kw: _fake_completion(json.dumps(payload)))
    result = groq_service.run_ai_analysis(_ret(), [img], [], [], ["STANDARD"])
    assert result.status == "OK"
    assert [c["name"] for c in result.components] == ["charger"]


def test_invalid_grade_is_rejected_by_schema():
    with pytest.raises(Exception):
        QwenInspectionResponse.model_validate({
            "identity": "PASS", "condition_grade": "MINTY-FRESH",
            "components": [], "visible_defects": [], "confidence": 0.5,
        })


def test_invalid_identity_value_is_rejected():
    with pytest.raises(Exception):
        QwenInspectionResponse.model_validate({
            "identity": "MAYBE", "condition_grade": "A_NEW",
            "components": [], "visible_defects": [],
        })


def test_malformed_json_reports_malformed(monkeypatch, tmp_path):
    from agents.returns.backend.app.core.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    img = tmp_path / "p.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0x")
    _patch_client(monkeypatch, lambda **kw: _fake_completion("this is not json at all"))
    result = groq_service.run_ai_analysis(_ret(), [img], [], [], ["STANDARD"])
    assert result.status == "MALFORMED"
    assert result.error and "malformed" in result.error


def test_rate_limit_reports_rate_limited(monkeypatch, tmp_path):
    from agents.returns.backend.app.core.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    monkeypatch.setattr(settings, "groq_max_retries", 1)
    img = tmp_path / "p.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0x")

    class RateLimitError(Exception):
        status_code = 429

    calls = {"n": 0}

    def raise_429(**kw):
        calls["n"] += 1
        raise RateLimitError("429 rate limit exceeded")

    _patch_client(monkeypatch, raise_429)
    monkeypatch.setattr(groq_service.time, "sleep", lambda s: None)
    result = groq_service.run_ai_analysis(_ret(), [img], [], [], ["STANDARD"])
    assert result.status == "RATE_LIMITED"
    assert calls["n"] == 2  # initial attempt + bounded retry


def test_provider_failure_reports_failed(monkeypatch, tmp_path):
    from agents.returns.backend.app.core.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    img = tmp_path / "p.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0x")

    def boom(**kw):
        raise RuntimeError("certificate verify failed")

    _patch_client(monkeypatch, boom)
    result = groq_service.run_ai_analysis(_ret(), [img], [], [], ["STANDARD"])
    assert result.status == "FAILED"
    assert result.identity is None and result.condition_grade is None


def test_aidata_statuses_are_enum_bounded():
    from agents.returns.backend.app.models.enums import AIStatus

    for status in ("OK", "UNAVAILABLE", "TIMEOUT", "RATE_LIMITED", "MALFORMED", "FAILED"):
        assert status in AIStatus.ALL
    assert AIData(status="OK").status == "OK"
