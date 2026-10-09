"""Production startup guards, user management and health endpoint tests."""
from __future__ import annotations

import pytest

from tests.conftest import ADMIN_PASS, ADMIN_USER, login, make_agent


# ---------------------------------------------------------------------------
# Production guards
# ---------------------------------------------------------------------------
def test_production_refuses_mock_sms():
    from app.core.config import settings
    from app.main import _ensure_production_safety

    original = (settings.app_env, settings.sms_provider)
    try:
        settings.app_env = "production"
        settings.sms_provider = "mock"
        with pytest.raises(RuntimeError, match="mock"):
            _ensure_production_safety()
    finally:
        settings.app_env, settings.sms_provider = original


def test_production_refuses_default_secret():
    from app.core.config import settings
    from app.main import _ensure_production_safety

    original = (settings.app_env, settings.secret_key)
    try:
        settings.app_env = "production"
        settings.sms_provider = "twilio"
        settings.secret_key = "CHANGE-ME-DEV-ONLY-insecure-secret"
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            _ensure_production_safety()
    finally:
        settings.app_env, settings.secret_key = original


def test_production_ok_with_real_provider_config():
    from app.core.config import settings
    from app.main import _ensure_production_safety

    original = (settings.app_env, settings.sms_provider, settings.secret_key)
    try:
        settings.app_env = "production"
        settings.sms_provider = "twilio"
        settings.secret_key = "a-sufficiently-long-random-secret-value"
        _ensure_production_safety()  # must not raise
    finally:
        settings.app_env, settings.sms_provider, settings.secret_key = original


def test_no_public_registration_route(client):
    for path in ("/api/auth/register", "/api/register", "/api/admin/signup"):
        assert client.post(path, json={"username": "x", "password": "yyyyyyyy"}).status_code in (404, 405)


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
def test_admin_creates_agent_and_verifies_phone(client, admin_headers):
    resp = client.post(
        "/api/admin/users",
        json={"username": "newagent", "password": "new-agent-pass-1", "role": "AGENT",
              "phone": "+15551234567", "phone_verified": True},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    user = resp.json()
    assert user["role"] == "AGENT" and user["phone_verified"] is True
    # Phone change resets verification.
    upd = client.put(f"/api/admin/users/{user['id']}", json={"phone": "+15559999999"}, headers=admin_headers)
    assert upd.status_code == 200 and upd.json()["phone_verified"] is False
    upd2 = client.put(f"/api/admin/users/{user['id']}", json={"phone_verified": True}, headers=admin_headers)
    assert upd2.json()["phone_verified"] is True


def test_duplicate_username_conflict(client, admin_headers, agent):
    resp = client.post(
        "/api/admin/users",
        json={"username": agent["username"], "password": "another-pass-99", "role": "AGENT"},
        headers=admin_headers,
    )
    assert resp.status_code == 409


def test_weak_password_rejected(client, admin_headers):
    resp = client.post(
        "/api/admin/users",
        json={"username": "weakpw", "password": "short", "role": "AGENT"},
        headers=admin_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
def test_health_reports_real_dependency_state(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert body["database"]["status"] == "ok"
    assert body["sms_provider"] == "mock"
    assert body["storage"]["writable"] is True
    assert body["ocr"]["configured_engine"] in ("auto", "rapidocr", "tesseract", "none")
    assert "configured_model_path" in body["yolo"]
    # No secrets leak.
    blob = str(body).lower()
    assert "secret" not in blob and "token" not in blob


def test_openapi_schema_generated(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/returns" in paths and "/api/otp/verify" in paths and "/api/inspections" in paths
