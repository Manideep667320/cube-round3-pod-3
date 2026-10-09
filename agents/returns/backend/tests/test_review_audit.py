"""Human review and audit trail tests."""
from __future__ import annotations

from agents.returns.backend.tests.conftest import run_full_flow_to_inspection, image_bytes, upload_image


def _inspection_in_review(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok) -> dict:
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    headers = {"Authorization": f"Bearer {state['verify']['inspection_token']}"}
    inspection = upload_image(client, headers, image_bytes()).json()
    assert inspection["decision"]["outcome"] == "MANUAL_REVIEW"
    return {"state": state, "inspection": inspection}


def _resolve(client, admin_headers, inspection_id: str, outcome: str, reason: str = "Verified photo manually"):
    return client.post(
        f"/api/inspections/{inspection_id}/resolve",
        json={"outcome": outcome, "reason": reason},
        headers=admin_headers,
    )


def test_review_queue_lists_pending(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok):
    ctx = _inspection_in_review(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok)
    queue = client.get("/api/review-queue", headers=admin_headers).json()
    ids = {item["id"] for item in queue}
    assert ctx["inspection"]["id"] in ids
    item = next(i for i in queue if i["id"] == ctx["inspection"]["id"])
    assert item["return_code"] and item["expected_sku"]


def test_resolve_review_override_preserves_automated_decision(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok):
    ctx = _inspection_in_review(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok)
    inspection_id = ctx["inspection"]["id"]
    automated = ctx["inspection"]["decision"]["outcome"]

    resp = _resolve(client, admin_headers, inspection_id, "APPROVE", reason="Photo shows all items; label glare")
    assert resp.status_code == 201, resp.text
    review = resp.json()
    assert review["outcome"] == "APPROVE"
    assert review["overrides_automated"] is (automated != "APPROVE")
    assert review["reason"]

    # Original automated decision is preserved untouched.
    detail = client.get(f"/api/inspections/{inspection_id}", headers=admin_headers).json()
    assert detail["decision"]["outcome"] == automated
    assert detail["reviews"][0]["outcome"] == "APPROVE"
    assert detail["reviews"][0]["overrides_automated"] is True
    # Return closes as approved.
    ret = client.get(f"/api/returns/{ctx['state']['return']['id']}", headers=admin_headers).json()
    assert ret["status"] == "APPROVED"


def test_resolve_requires_reason(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok):
    ctx = _inspection_in_review(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok)
    resp = client.post(
        f"/api/inspections/{ctx['inspection']['id']}/resolve",
        json={"outcome": "APPROVE", "reason": "x"},
        headers=admin_headers,
    )
    assert resp.status_code == 422  # reason min_length=5


def test_cannot_resolve_twice(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok):
    ctx = _inspection_in_review(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok)
    inspection_id = ctx["inspection"]["id"]
    assert _resolve(client, admin_headers, inspection_id, "REJECT").status_code == 201
    second = _resolve(client, admin_headers, inspection_id, "APPROVE")
    assert second.status_code == 409


def test_agents_cannot_resolve_reviews(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok):
    ctx = _inspection_in_review(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok)
    resp = client.post(
        f"/api/inspections/{ctx['inspection']['id']}/resolve",
        json={"outcome": "APPROVE", "reason": "Let me approve my own work"},
        headers=agent_headers,
    )
    assert resp.status_code == 403


def test_audit_trail_records_full_workflow(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok):
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    headers = {"Authorization": f"Bearer {state['verify']['inspection_token']}"}
    upload_image(client, headers, image_bytes())

    events = client.get("/api/audit", params={"limit": 500}, headers=admin_headers).json()
    actions = {e["action"] for e in events}
    expected = {
        "LOGIN_SUCCESS", "RETURN_CREATED", "QR_GENERATED", "QR_SCANNED",
        "OTP_ISSUED", "OTP_VERIFIED", "INSPECTION_CREATED", "DECISION_RECORDED",
    }
    assert expected.issubset(actions), f"missing audit actions: {expected - actions}"
    # No secrets in audit details.
    import json as _json

    for e in events:
        blob = _json.dumps(e["details"]).lower()
        for secret_word in ("password", "\"code\"", "token\":"):
            assert secret_word not in blob


def test_audit_filtered_by_entity(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok):
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    events = client.get(
        "/api/audit",
        params={"entity_type": "return", "entity_id": state["return"]["id"]},
        headers=admin_headers,
    ).json()
    assert events
    assert all(e["entity_id"] == state["return"]["id"] for e in events)
