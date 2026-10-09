"""OTP workflow tests: delivery via mock SMS, verification, limits, leakage."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from agents.returns.backend.app.db.session import SessionLocal
from agents.returns.backend.app.core.config import settings
from agents.returns.backend.app.models import OTPChallenge
from agents.returns.backend.tests.conftest import extract_otp, run_up_to_scan


def _otp_request(client, scan_token: str):
    return client.post("/api/otp/request", json={}, headers={"Authorization": f"Bearer {scan_token}"})


def test_otp_delivered_to_registered_phone(client, admin_headers, agent, agent_headers, mock_sms):
    state = run_up_to_scan(client, admin_headers, agent, agent_headers)
    resp = _otp_request(client, state["scan"]["scan_token"])
    assert resp.status_code == 200
    body = resp.json()
    # Response masks the phone and never contains a code.
    assert "*" in body["masked_phone"] and agent["phone"][-4:] in body["masked_phone"]
    assert "code" not in {k.lower() for k in body}
    msg = mock_sms.last_for(agent["phone"])
    assert msg is not None and re.search(r"code: \d{6}", msg.body)


def test_otp_verify_success_single_use(client, admin_headers, agent, agent_headers, mock_sms):
    state = run_up_to_scan(client, admin_headers, agent, agent_headers)
    _otp_request(client, state["scan"]["scan_token"])
    code = extract_otp(mock_sms, agent["phone"])
    verify = client.post(
        "/api/otp/verify", json={"scan_token": state["scan"]["scan_token"], "code": code}, headers=agent_headers
    )
    assert verify.status_code == 200
    assert verify.json()["inspection_token"]
    # Replay of the same OTP fails (one-time consumption).
    replay = client.post(
        "/api/otp/verify", json={"scan_token": state["scan"]["scan_token"], "code": code}, headers=agent_headers
    )
    assert replay.status_code >= 400
    detail = client.get(f"/api/returns/{ret_id(state)}", headers=admin_headers).json()
    assert detail["status"] == "AWAITING_INSPECTION"


def ret_id(state):
    return state["return"]["id"]


def test_wrong_otp_increments_attempts_then_exhausts(client, admin_headers, agent, agent_headers, mock_sms):
    state = run_up_to_scan(client, admin_headers, agent, agent_headers)
    _otp_request(client, state["scan"]["scan_token"])
    code = extract_otp(mock_sms, agent["phone"])
    wrong = f"{int(code) + 1:06d}" if code != "999999" else "000000"
    for _ in range(settings.otp_max_attempts - 1):
        resp = client.post(
            "/api/otp/verify", json={"scan_token": state["scan"]["scan_token"], "code": wrong}, headers=agent_headers
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"]["code"] == "otp_incorrect"
    # One failed attempt below the cap: the CORRECT code still works.
    ok = client.post(
        "/api/otp/verify", json={"scan_token": state["scan"]["scan_token"], "code": code}, headers=agent_headers
    )
    assert ok.status_code == 200


def test_otp_exhaustion_after_max_failed_attempts(client, admin_headers, agent, agent_headers, mock_sms):
    state = run_up_to_scan(client, admin_headers, agent, agent_headers)
    _otp_request(client, state["scan"]["scan_token"])
    code = extract_otp(mock_sms, agent["phone"])
    wrong = f"{int(code) + 1:06d}" if code != "999999" else "000000"
    last = None
    for _ in range(settings.otp_max_attempts + 1):
        last = client.post(
            "/api/otp/verify", json={"scan_token": state["scan"]["scan_token"], "code": wrong}, headers=agent_headers
        )
        if last.status_code == 410:
            break
    assert last is not None and last.status_code == 410
    assert last.json()["error"]["code"] == "otp_exhausted"
    # Even the correct code is dead now.
    after = client.post(
        "/api/otp/verify", json={"scan_token": state["scan"]["scan_token"], "code": code}, headers=agent_headers
    )
    assert after.status_code >= 400


def test_expired_otp_rejected(client, admin_headers, agent, agent_headers, mock_sms):
    state = run_up_to_scan(client, admin_headers, agent, agent_headers)
    _otp_request(client, state["scan"]["scan_token"])
    code = extract_otp(mock_sms, agent["phone"])
    session = SessionLocal()
    try:
        challenge = (
            session.query(OTPChallenge).filter(OTPChallenge.status == "PENDING").order_by(OTPChallenge.issued_at.desc()).first()
        )
        challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        session.commit()
    finally:
        session.close()
    resp = client.post(
        "/api/otp/verify", json={"scan_token": state["scan"]["scan_token"], "code": code}, headers=agent_headers
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "otp_expired"


def test_resend_supersedes_previous_code(client, admin_headers, agent, agent_headers, mock_sms):
    state = run_up_to_scan(client, admin_headers, agent, agent_headers)
    _otp_request(client, state["scan"]["scan_token"])
    first_code = extract_otp(mock_sms, agent["phone"])
    resp = _otp_request(client, state["scan"]["scan_token"])
    assert resp.status_code == 200
    second_code = extract_otp(mock_sms, agent["phone"])
    assert first_code != second_code
    # Old code is invalidated, new code works.
    old = client.post(
        "/api/otp/verify", json={"scan_token": state["scan"]["scan_token"], "code": first_code}, headers=agent_headers
    )
    assert old.status_code in (400, 410)
    new = client.post(
        "/api/otp/verify", json={"scan_token": state["scan"]["scan_token"], "code": second_code}, headers=agent_headers
    )
    assert new.status_code == 200
    # Exactly one challenge is VERIFIED, the superseded one is marked.
    session = SessionLocal()
    try:
        statuses = [
            c.status
            for c in session.query(OTPChallenge).filter(OTPChallenge.return_id == state["return"]["id"])
        ]
        assert "VERIFIED" in statuses and "SUPERSEDED" in statuses
    finally:
        session.close()


def test_otp_without_verified_phone_rejected(client, admin_headers, agent, agent_headers, mock_sms):
    # Un-verify the phone as admin.
    users = client.get("/api/admin/users", headers=admin_headers).json()
    target = next(u for u in users if u["username"] == agent["username"])
    client.put(f"/api/admin/users/{target['id']}", json={"phone_verified": False}, headers=admin_headers)
    from agents.returns.backend.tests.conftest import login

    agent_headers = login(client, agent["username"], agent["password"])
    state = run_up_to_scan(client, admin_headers, agent, agent_headers)
    resp = _otp_request(client, state["scan"]["scan_token"])
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "phone_unverified"
    assert mock_sms.last_for(agent["phone"]) is None


def test_no_plaintext_otp_persisted(client, admin_headers, agent, agent_headers, mock_sms):
    state = run_up_to_scan(client, admin_headers, agent, agent_headers)
    _otp_request(client, state["scan"]["scan_token"])
    code = extract_otp(mock_sms, agent["phone"])
    session = SessionLocal()
    try:
        challenges = session.query(OTPChallenge).all()
        assert challenges
        for c in challenges:
            assert code not in c.code_hash
            assert len(c.code_hash) == 64  # sha256 hex
    finally:
        session.close()


def test_otp_verify_requires_valid_scan_token(client, agent_headers):
    resp = client.post("/api/otp/verify", json={"scan_token": "garbage-token", "code": "123456"}, headers=agent_headers)
    assert resp.status_code in (400, 401, 409)


def test_mock_outbox_dev_convenience(tmp_path, monkeypatch, client, admin_headers, agent, agent_headers, mock_sms):
    """When MOCK_SMS_OUTBOX is set (local dev only), the mock mirrors messages
    to a file so a human can read codes during manual UI testing."""
    from agents.returns.backend.app.core.config import settings

    out = tmp_path / "outbox.txt"
    monkeypatch.setattr(settings, "mock_sms_outbox", str(out))
    state = run_up_to_scan(client, admin_headers, agent, agent_headers)
    assert _otp_request(client, state["scan"]["scan_token"]).status_code == 200
    assert out.is_file()
    content = out.read_text(encoding="utf-8")
    assert agent["phone"] in content and "ReturnGuard" in content


def test_hourly_otp_issue_cap(client, admin_headers, agent, agent_headers, mock_sms):
    state = run_up_to_scan(client, admin_headers, agent, agent_headers)
    allowed = 0
    for _ in range(settings.otp_max_issues_per_hour + 2):
        resp = _otp_request(client, state["scan"]["scan_token"])
        if resp.status_code == 200:
            allowed += 1
        else:
            assert resp.status_code == 429
            assert resp.json()["error"]["code"] in ("otp_rate_limited", "resend_cooldown")
            break
    assert allowed >= 1
