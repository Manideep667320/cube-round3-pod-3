"""QR authorization tests: generation, scanning, replay, revocation, expiry."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models import QRAuthorization
from tests.conftest import create_return, make_agent


def test_generate_qr_requires_assigned_agent(client, admin_headers):
    ret = create_return(client, admin_headers, agent_id=None)
    resp = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "agent_required"


def test_generate_qr_hides_secret_and_returns_png(client, admin_headers, agent):
    ret = create_return(client, admin_headers, agent_id=agent["id"])
    resp = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["token"]) >= 40, "QR token must be high entropy"
    assert body["qr_authorization"]["status"] == "ACTIVE"
    png = base64.b64decode(body["qr_png_base64"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert body["scan_value"].endswith(body["token"])
    # The QR must not embed OTP/phone/credentials.
    for forbidden in ("otp", "phone", "password", "secret_key"):
        assert forbidden not in body["scan_value"].lower()


def test_raw_token_never_persisted(client, admin_headers, agent):
    ret = create_return(client, admin_headers, agent_id=agent["id"])
    body = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers).json()
    raw = body["token"]
    session = SessionLocal()
    try:
        rows = session.query(QRAuthorization).all()
        for row in rows:
            assert raw not in (row.token_hash, row.token_prefix), "raw QR secret stored at rest!"
            assert row.token_hash != raw
    finally:
        session.close()


def test_agent_scans_qr_successfully(client, admin_headers, agent, agent_headers):
    ret = create_return(client, admin_headers, agent_id=agent["id"])
    qr = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers).json()
    resp = client.post("/api/qr/scan", json={"token": qr["token"]}, headers=agent_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["return_id"] == ret["id"]
    assert body["scan_token"]
    # Return moves to AWAITING_OTP.
    detail = client.get(f"/api/returns/{ret['id']}", headers=admin_headers).json()
    assert detail["status"] == "AWAITING_OTP"


def test_qr_replay_rejected(client, admin_headers, agent, agent_headers):
    ret = create_return(client, admin_headers, agent_id=agent["id"])
    qr = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers).json()
    first = client.post("/api/qr/scan", json={"token": qr["token"]}, headers=agent_headers)
    assert first.status_code == 200
    second = client.post("/api/qr/scan", json={"token": qr["token"]}, headers=agent_headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "qr_replayed"


def test_wrong_agent_cannot_use_qr(client, admin_headers, agent, client_2=None):
    from tests.conftest import login

    other = make_agent(client, admin_headers, username="agent_other", phone="+15550000002")
    other_headers = login(client, other["username"], other["password"])
    ret = create_return(client, admin_headers, agent_id=agent["id"])
    qr = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers).json()
    resp = client.post("/api/qr/scan", json={"token": qr["token"]}, headers=other_headers)
    assert resp.status_code == 403
    # And the failure is audited.
    events = client.get("/api/audit", params={"action": "QR_SCAN_REJECTED"}, headers=admin_headers).json()
    assert events, "rejected scan must be audited"


def test_guessed_token_rejected(client, agent_headers):
    resp = client.post("/api/qr/scan", json={"token": "AAAA" * 16}, headers=agent_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "qr_invalid"


def test_revoke_qr_blocks_scan(client, admin_headers, agent, agent_headers):
    ret = create_return(client, admin_headers, agent_id=agent["id"])
    qr = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers).json()
    revoke = client.post(f"/api/qr/{qr['qr_authorization']['id']}/revoke", headers=admin_headers)
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "REVOKED"
    resp = client.post("/api/qr/scan", json={"token": qr["token"]}, headers=agent_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "qr_revoked"
    # Return falls back to PENDING.
    detail = client.get(f"/api/returns/{ret['id']}", headers=admin_headers).json()
    assert detail["status"] == "PENDING"


def test_expired_qr_rejected(client, admin_headers, agent, agent_headers):
    ret = create_return(client, admin_headers, agent_id=agent["id"])
    qr = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers).json()
    session = SessionLocal()
    try:
        row = session.get(QRAuthorization, qr["qr_authorization"]["id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.commit()
    finally:
        session.close()
    resp = client.post("/api/qr/scan", json={"token": qr["token"]}, headers=agent_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "qr_expired"


def test_regenerating_qr_revokes_previous(client, admin_headers, agent, agent_headers):
    ret = create_return(client, admin_headers, agent_id=agent["id"])
    first = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers).json()
    second = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers).json()
    assert first["token"] != second["token"]
    resp = client.post("/api/qr/scan", json={"token": first["token"]}, headers=agent_headers)
    assert resp.status_code == 409  # previous QR revoked by regeneration


def test_agent_only_sees_own_returns(client, admin_headers, agent, agent_headers):
    from tests.conftest import login

    other = make_agent(client, admin_headers, username="agent_scope", phone="+15550000003")
    mine = create_return(client, admin_headers, agent_id=agent["id"])
    _ = create_return(client, admin_headers, agent_id=other["id"])
    resp = client.get("/api/returns/me/assigned", headers=agent_headers)
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()}
    assert mine["id"] in ids
    assert len(ids) == 1
