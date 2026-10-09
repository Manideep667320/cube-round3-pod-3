"""Inspection pipeline tests: uploads, validation, evidence, decisions."""
from __future__ import annotations

from tests.conftest import (
    create_return,
    fake_detections_ok,
    fake_detections_unavailable,
    fake_ocr_no_text,
    fake_ocr_ok,
    fake_ocr_unavailable,
    image_bytes,
    run_full_flow_to_inspection,
    upload_image,
)


def test_upload_requires_otp_verified_token(client, agent_headers, admin_headers, agent):
    # No inspection token at all.
    resp = upload_image(client, agent_headers, image_bytes())
    assert resp.status_code == 401


def test_invalid_file_rejected(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok):
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    headers = {"Authorization": f"Bearer {state['verify']['inspection_token']}"}
    resp = upload_image(client, headers, b"this is definitely not an image", filename="evil.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] in ("invalid_image", "corrupt_image")


def test_oversized_file_rejected(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok):
    from app.core.config import settings

    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    headers = {"Authorization": f"Bearer {state['verify']['inspection_token']}"}
    big = b"\xff\xd8\xff\xe0" + b"\x00" * (settings.max_upload_bytes + 1024)
    resp = upload_image(client, headers, big)
    assert resp.status_code == 413


def test_full_pipeline_happy_path_persists_evidence(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok):
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    headers = {"Authorization": f"Bearer {state['verify']['inspection_token']}"}
    resp = upload_image(client, headers, image_bytes())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["ocr"]["status"] == "OK"
    assert "LAPTOP-X1-CARBON" in body["ocr"]["full_text"]
    run = body["detection_run"]
    assert run["status"] == "OK"
    assert any(d["class_label"] == "laptop" for d in run["detections"])
    for det in run["detections"]:
        x1, y1, x2, y2 = det["bbox"]
        assert x2 > x1 and y2 > y1
        assert 0 <= x1 < body["image"]["width"] and 0 <= x2 <= body["image"]["width"]
    evidence = body["evidence"]["payload"]
    # AI stage disabled in tests -> its absence is reported honestly.
    assert body["ai_analysis"]["status"] == "UNAVAILABLE"
    # Identity needs TWO sources; OCR-only stays UNCERTAIN.
    assert evidence["identity"]["verdict"] == "UNCERTAIN"
    comp_states = {c["name"]: c["observation"] for c in evidence["components"]}
    assert comp_states["laptop"] == "OBSERVED"
    # 'charger' has no detection -> not confirmed (never claimed missing).
    assert comp_states["charger"] in ("NOT_OBSERVED", "UNCERTAIN")
    assert body["decision"]["outcome"] == "MANUAL_REVIEW"
    assert body["decision"]["rationale"]
    detail = client.get(f"/api/returns/{state['return']['id']}", headers=admin_headers).json()
    assert detail["status"] == "NEEDS_REVIEW"
    assert detail["inspections"][0]["id"] == body["id"]


def test_auto_approve_when_all_dimensions_pass(client, admin_headers, agent, agent_headers, mock_sms,
                                               patch_fake_cv_ok, patch_fake_ai_ok):
    """With real OCR+YOLO faked and AI confirming identity + all components,
    the aggregated decision approves with a disposition."""
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    headers = {"Authorization": f"Bearer {state['verify']['inspection_token']}"}
    body = upload_image(client, headers, image_bytes()).json()
    assert body["ai_analysis"]["status"] == "OK"
    assert body["evidence"]["payload"]["identity"]["verdict"] == "PASS"
    assert body["decision"]["outcome"] == "APPROVE"
    assert body["decision"]["disposition"] == "RESTOCK"
    detail = client.get(f"/api/returns/{state['return']['id']}", headers=admin_headers).json()
    assert detail["status"] == "APPROVED"


def test_missing_model_routes_to_review_not_fabricated(client, admin_headers, agent, agent_headers, mock_sms, monkeypatch):
    from app.services import ocr_service, yolo_service

    monkeypatch.setattr(ocr_service, "run_ocr", lambda path: fake_ocr_ok())
    monkeypatch.setattr(yolo_service, "run_detection", lambda path: fake_detections_unavailable())
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    headers = {"Authorization": f"Bearer {state['verify']['inspection_token']}"}
    body = upload_image(client, headers, image_bytes()).json()
    assert body["detection_run"]["status"] == "MODEL_UNAVAILABLE"
    assert body["detection_run"]["detections"] == []
    assert body["decision"]["outcome"] == "MANUAL_REVIEW"


def test_ocr_unavailable_routes_to_review(client, admin_headers, agent, agent_headers, mock_sms, monkeypatch):
    from app.services import ocr_service, yolo_service

    monkeypatch.setattr(ocr_service, "run_ocr", lambda path: fake_ocr_unavailable())
    monkeypatch.setattr(yolo_service, "run_detection", lambda path: fake_detections_ok())
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    headers = {"Authorization": f"Bearer {state['verify']['inspection_token']}"}
    body = upload_image(client, headers, image_bytes()).json()
    assert body["ocr"]["status"] == "ENGINE_UNAVAILABLE"
    assert body["decision"]["outcome"] == "MANUAL_REVIEW"


def test_photo_without_text_is_useful(client, admin_headers, agent, agent_headers, mock_sms, monkeypatch):
    from app.services import ocr_service, yolo_service

    monkeypatch.setattr(ocr_service, "run_ocr", lambda path: fake_ocr_no_text())
    monkeypatch.setattr(yolo_service, "run_detection", lambda path: fake_detections_ok())
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    headers = {"Authorization": f"Bearer {state['verify']['inspection_token']}"}
    body = upload_image(client, headers, image_bytes()).json()
    assert body["ocr"]["status"] == "NO_TEXT_DETECTED"
    # The inspection still completes and stores detection evidence.
    assert body["detection_run"]["status"] == "OK"
    assert body["decision"]["outcome"] == "MANUAL_REVIEW"  # identity unconfirmed


def test_other_agent_cannot_view_inspection_or_image(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok, monkeypatch):
    from tests.conftest import login, make_agent

    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    headers = {"Authorization": f"Bearer {state['verify']['inspection_token']}"}
    inspection = upload_image(client, headers, image_bytes()).json()

    other = make_agent(client, admin_headers, username="agent_peeper", phone="+15550000009")
    other_headers = login(client, other["username"], other["password"])
    assert client.get(f"/api/inspections/{inspection['id']}", headers=other_headers).status_code == 404
    assert client.get(f"/api/inspections/{inspection['id']}/image", headers=other_headers).status_code == 404
    # Unauthenticated access is rejected as well.
    assert client.get(f"/api/inspections/{inspection['id']}/image").status_code == 401
    # The owning agent and the admin can fetch both.
    assert client.get(f"/api/inspections/{inspection['id']}", headers=agent_headers).status_code == 200
    img = client.get(f"/api/inspections/{inspection['id']}/image", headers=agent_headers)
    assert img.status_code == 200 and img.headers["content-type"].startswith("image/")
    assert client.get(f"/api/inspections/{inspection['id']}", headers=admin_headers).status_code == 200


def test_duplicate_upload_blocked_after_flow(client, admin_headers, agent, agent_headers, mock_sms, patch_fake_cv_ok):
    """The inspection token is single-purpose; a second upload with a stale
    token for a closed return must not silently double-process."""
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    headers = {"Authorization": f"Bearer {state['verify']['inspection_token']}"}
    first = upload_image(client, headers, image_bytes())
    assert first.status_code == 201
    # After the automated decision the return is closed; a fresh scan of the
    # same (already used) QR fails, so a new inspection cannot be started.
    scan_again = client.post("/api/qr/scan", json={"token": state["qr"]["token"]}, headers=agent_headers)
    assert scan_again.status_code == 409
