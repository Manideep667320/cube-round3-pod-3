"""Authentication, session and role-restriction tests."""
from __future__ import annotations

from tests.conftest import ADMIN_PASS, ADMIN_USER, login


def test_login_success_returns_token_and_user(client):
    resp = client.post("/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["role"] == "ADMIN"
    assert body["token_type"] == "bearer"


def test_login_wrong_password_rejected(client):
    resp = client.post("/api/auth/login", json={"username": ADMIN_USER, "password": "wrong-password"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_user_same_error(client):
    resp = client.post("/api/auth/login", json={"username": "ghost-user-x", "password": "whatever123"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_token(client, admin_headers):
    resp = client.get("/api/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == ADMIN_USER


def test_agent_cannot_access_admin_endpoints(client, agent_headers):
    for path in ("/api/returns", "/api/admin/users", "/api/review-queue", "/api/audit", "/api/stats"):
        resp = client.get(path, headers=agent_headers)
        assert resp.status_code == 403, f"{path} should be admin-only, got {resp.status_code}"


def test_admin_cannot_use_agent_flow_endpoints(client, admin_headers):
    resp = client.post("/api/qr/scan", json={"token": "some-token-value-123456"}, headers=admin_headers)
    assert resp.status_code == 403


def test_missing_or_malformed_token(client):
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_login_rate_limiting(client, monkeypatch):
    from app.core.config import settings
    from app.core.ratelimit import login_limiter

    login_limiter.reset()
    monkeypatch.setattr(settings, "login_rate_limit_attempts", 3)
    monkeypatch.setattr(settings, "login_rate_limit_window_seconds", 300)
    try:
        last = None
        for _ in range(6):
            last = client.post("/api/auth/login", json={"username": ADMIN_USER, "password": "bad-password-x"})
            if last.status_code == 429:
                break
        assert last is not None and last.status_code == 429, "rate limiter did not engage"
    finally:
        login_limiter.reset()
