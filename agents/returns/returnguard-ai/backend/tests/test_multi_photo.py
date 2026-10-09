"""Multi-photo inspections: aggregation, contents-layout evidence, duplicates."""
from __future__ import annotations

from tests.conftest import (
    fake_ai_ok,
    fake_detections_ok,
    fake_ocr_ok,
    image_bytes,
    run_full_flow_to_inspection,
    upload_image,
)


def _patch(monkeypatch, ai_observed: tuple[str, ...]):
    from app.services import groq_service, ocr_service, yolo_service

    monkeypatch.setattr(ocr_service, "run_ocr", lambda path: fake_ocr_ok())
    monkeypatch.setattr(yolo_service, "run_detection",
                        lambda path: fake_detections_ok([("laptop", 0.9)]))
    monkeypatch.setattr(
        groq_service, "run_ai_analysis",
        lambda ret, image_paths, ocr_texts, detections, view_types: fake_ai_ok(
            components={c.name: c.name in ai_observed for c in ret.expected_components}
        ),
    )


def _upload(client, token: str, data: bytes, view_type: str = "STANDARD", name: str = "p.jpg"):
    return upload_image(client, {"Authorization": f"Bearer {token}"}, data, filename=name,
                        view_type=view_type)


def test_second_view_can_confirm_missing(client, admin_headers, agent, agent_headers, mock_sms, monkeypatch):
    _patch(monkeypatch, ai_observed=("laptop",))
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    token = state["verify"]["inspection_token"]

    first = _upload(client, token, image_bytes(color=(10, 10, 10)))
    assert first.status_code == 201
    assert first.json()["decision"]["outcome"] == "MANUAL_REVIEW"

    layout = _upload(client, token, image_bytes(color=(200, 30, 30)), view_type="CONTENTS_LAYOUT")
    assert layout.status_code == 201
    body = layout.json()
    rationale_text = " ".join(r["explanation"] for r in body["decision"]["rationale"])
    assert "Confirmed missing" in rationale_text and "charger" in rationale_text
    assert body["decision"]["outcome"] == "MANUAL_REVIEW"
    # Missing accessory downgrades RESTOCK to REFURBISH.
    assert body["decision"]["disposition"] == "REFURBISH"
    assert body["view_type"] == "CONTENTS_LAYOUT"


def test_extra_photo_with_all_parts_approves(client, admin_headers, agent, agent_headers, mock_sms, monkeypatch):
    from app.services import groq_service, ocr_service, yolo_service

    monkeypatch.setattr(ocr_service, "run_ocr", lambda path: fake_ocr_ok())
    monkeypatch.setattr(yolo_service, "run_detection",
                        lambda path: fake_detections_ok([("laptop", 0.9)]))
    seen: list[str] = []

    def ai(ret, image_paths, ocr_texts, detections, view_types):
        seen.append(view_types[0])
        # Second photo reveals the charger.
        observed = ("laptop", "charger") if len(seen) > 1 else ("laptop",)
        return fake_ai_ok(components={c.name: c.name in observed for c in ret.expected_components})

    monkeypatch.setattr(groq_service, "run_ai_analysis", ai)
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    token = state["verify"]["inspection_token"]

    assert _upload(client, token, image_bytes(color=(1, 2, 3))).status_code == 201
    second = _upload(client, token, image_bytes(color=(4, 5, 6)))
    assert second.status_code == 201
    body = second.json()
    assert body["decision"]["outcome"] == "APPROVE"
    assert body["decision"]["disposition"] == "RESTOCK"


def test_duplicate_photo_rejected(client, admin_headers, agent, agent_headers, mock_sms, monkeypatch):
    _patch(monkeypatch, ai_observed=("laptop", "charger"))
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    token = state["verify"]["inspection_token"]

    data = image_bytes(color=(7, 7, 7))
    first = _upload(client, token, data)
    assert first.status_code == 201
    dup = _upload(client, token, data, name="same-bytes.jpg")
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "duplicate_upload"


def test_invalid_view_type_falls_back_to_standard(client, admin_headers, agent, agent_headers, mock_sms, monkeypatch):
    _patch(monkeypatch, ai_observed=("laptop",))
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    token = state["verify"]["inspection_token"]
    resp = _upload(client, token, image_bytes(color=(9, 9, 9)), view_type="TELEMETRY")
    assert resp.status_code == 201
    assert resp.json()["view_type"] == "STANDARD"


def test_every_photo_attached_to_correct_return(client, admin_headers, agent, agent_headers, mock_sms, monkeypatch):
    _patch(monkeypatch, ai_observed=("laptop",))
    state = run_full_flow_to_inspection(client, admin_headers, agent, agent_headers, mock_sms)
    token = state["verify"]["inspection_token"]
    first = _upload(client, token, image_bytes(color=(11, 11, 11))).json()
    second = _upload(client, token, image_bytes(color=(22, 22, 22))).json()
    assert first["return_id"] == state["return"]["id"] == second["return_id"]
    assert first["id"] != second["id"]
    detail = client.get(f"/api/returns/{state['return']['id']}", headers=admin_headers).json()
    assert len(detail["inspections"]) == 2
