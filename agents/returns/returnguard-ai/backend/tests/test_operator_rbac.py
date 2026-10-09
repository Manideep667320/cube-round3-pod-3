"""Inspection-operator (warehouse) role tests.

Operators can run the full inspection flow on ASSIGNED returns, exactly like
delivery agents; they hold no admin powers anywhere.
"""
from __future__ import annotations

from tests.conftest import create_return, extract_otp, image_bytes, login, upload_image


def _make_operator(client, admin_headers, username="warehouse_op", phone="+15550000020"):
    resp = client.post(
        "/api/admin/users",
        json={"username": username, "password": "op-pass-12345", "role": "OPERATOR",
              "phone": phone, "phone_verified": True},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    user = resp.json()
    return {"id": user["id"], "username": username, "phone": phone, "password": "op-pass-12345"}


def test_operator_runs_full_inspection_flow(client, admin_headers, mock_sms, patch_fake_cv_ok):
    op = _make_operator(client, admin_headers)
    op_headers = login(client, op["username"], op["password"])

    ret = create_return(client, admin_headers, agent_id=op["id"])
    qr = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers).json()
    scan = client.post("/api/qr/scan", json={"token": qr["token"]}, headers=op_headers)
    assert scan.status_code == 200, scan.text

    otp_req = client.post("/api/otp/request", json={},
                          headers={"Authorization": f"Bearer {scan.json()['scan_token']}"})
    assert otp_req.status_code == 200
    code = extract_otp(mock_sms, op["phone"])
    verify = client.post("/api/otp/verify",
                         json={"scan_token": scan.json()["scan_token"], "code": code},
                         headers=op_headers)
    assert verify.status_code == 200
    inspection_token = verify.json()["inspection_token"]

    upload = upload_image(client, {"Authorization": f"Bearer {inspection_token}"}, image_bytes())
    assert upload.status_code == 201, upload.text
    assert upload.json()["status"] == "COMPLETED"


def test_operator_cannot_use_admin_endpoints(client, admin_headers):
    op = _make_operator(client, admin_headers, username="warehouse_op2", phone="+15550000021")
    headers = login(client, op["username"], op["password"])
    for path in ("/api/returns", "/api/admin/users", "/api/review-queue", "/api/audit",
                 "/api/stats", "/api/catalogue/new" ):
        if path.endswith("/new"):
            resp = client.post("/api/catalogue", json={"sku": "S", "name": "n"}, headers=headers)
        else:
            resp = client.get(path, headers=headers)
        assert resp.status_code == 403, f"{path} must stay admin-only, got {resp.status_code}"


def test_operator_cannot_scan_others_qr(client, admin_headers, agent):
    op = _make_operator(client, admin_headers, username="warehouse_op3", phone="+15550000022")
    op_headers = login(client, op["username"], op["password"])
    ret = create_return(client, admin_headers, agent_id=agent["id"])  # assigned to AGENT
    qr = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers).json()
    resp = client.post("/api/qr/scan", json={"token": qr["token"]}, headers=op_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "not_assigned"


def test_admin_cannot_use_operator_flow_endpoints(client, admin_headers):
    # Admins hold management powers, not inspection powers.
    resp = client.post("/api/qr/scan", json={"token": "some-token-value-123456"}, headers=admin_headers)
    assert resp.status_code == 403
