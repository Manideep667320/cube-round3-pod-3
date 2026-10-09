"""Shared test fixtures.

Environment is isolated BEFORE any app import:
- throwaway SQLite database and storage directory
- mock SMS provider (development/test only)
- deterministic bootstrap admin

External CV engines are replaced by deterministic fakes in app-logic tests;
tests marked `live_cv` exercise the real OCR engine and YOLO weights.
"""
from __future__ import annotations

import io
import os
import re
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="returndata-test-"))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["STORAGE_DIR"] = str(_TMP / "uploads")
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production-0123456789"
os.environ["SMS_PROVIDER"] = "mock"
os.environ["ADMIN_BOOTSTRAP_USERNAME"] = "testadmin"
os.environ["ADMIN_BOOTSTRAP_PASSWORD"] = "test-admin-pass-123"
os.environ["OTP_RESEND_COOLDOWN_SECONDS"] = "0"  # cooldown tested explicitly with its own setting override
os.environ["LOGIN_RATE_LIMIT_ATTEMPTS"] = "1000"  # real limiter tested explicitly in test_auth
os.environ["OCR_ENGINE"] = "auto"
# Deterministic AI stage for app-logic tests: key disabled (a real key in a
# local .env must never leak into tests or trigger live API calls).
# The pristine key is read straight from backend/.env WITHOUT importing the
# app config module (an early import would freeze the .env value into the
# settings singleton before the override below takes effect).
from pathlib import Path as _EnvPath  # noqa: E402


def _read_env_file_key() -> str:
    env_file = _EnvPath(__file__).resolve().parents[1] / ".env"
    if env_file.is_file():
        for _line in env_file.read_text(encoding="utf-8").splitlines():
            if _line.startswith("GROQ_API_KEY="):
                return _line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


_ORIGINAL_GROQ_KEY = _read_env_file_key()
os.environ["GROQ_API_KEY"] = ""
os.environ["GROQ_TIMEOUT_SECONDS"] = "5"
os.environ["GROQ_MAX_RETRIES"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import app  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.services.groq_service import AIData  # noqa: E402
from app.services.ocr_service import OCRData, OCRBlock  # noqa: E402
from app.services.sms_service import MockSMSProvider, get_sms_provider  # noqa: E402
from app.services.yolo_service import DetectionData, DetectionItem  # noqa: E402

ADMIN_USER = "testadmin"
ADMIN_PASS = "test-admin-pass-123"


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def mock_sms() -> MockSMSProvider:
    provider = get_sms_provider()
    assert isinstance(provider, MockSMSProvider), "tests require SMS_PROVIDER=mock"
    provider.clear()
    return provider


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture()
def admin_headers(client: TestClient) -> dict[str, str]:
    return login(client, ADMIN_USER, ADMIN_PASS)


def make_agent(client: TestClient, admin_headers: dict, username: str = "agent1", phone: str = "+15550000001") -> dict:
    resp = client.post(
        "/api/admin/users",
        json={
            "username": username,
            "password": "agent-pass-12345",
            "role": "AGENT",
            "full_name": "Test Agent",
            "phone": phone,
            "phone_verified": True,
        },
        headers=admin_headers,
    )
    assert resp.status_code in (201, 409), resp.text
    user_id = resp.json()["id"] if resp.status_code == 201 else _find_user(client, admin_headers, username)
    return {"id": user_id, "username": username, "phone": phone, "password": "agent-pass-12345"}


def _find_user(client: TestClient, admin_headers: dict, username: str) -> str:
    users = client.get("/api/admin/users", headers=admin_headers).json()
    return next(u["id"] for u in users if u["username"] == username)


@pytest.fixture()
def agent(client: TestClient, admin_headers: dict) -> dict:
    return make_agent(client, admin_headers, username=f"agent_{os.urandom(3).hex()}")


@pytest.fixture()
def agent_headers(client: TestClient, agent: dict) -> dict[str, str]:
    return login(client, agent["username"], agent["password"])


def create_return(client: TestClient, admin_headers: dict, agent_id: str | None = None,
                  sku: str = "LAPTOP-X1-CARBON", components: list[dict] | None = None) -> dict:
    payload = {
        "order_reference": "ORD-998877",
        "expected_sku": sku,
        "product_description": "ThinkPad X1 Carbon laptop return",
        "expected_components": components if components is not None else [
            {"name": "laptop", "yolo_class_hints": ["laptop"], "ocr_text_hint": ""},
            {"name": "charger", "yolo_class_hints": ["charger"], "ocr_text_hint": ""},
        ],
        "assigned_agent_id": agent_id,
    }
    resp = client.post("/api/returns", json=payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def extract_otp(mock_sms: MockSMSProvider, phone: str) -> str:
    msg = mock_sms.last_for(phone)
    assert msg is not None, "no SMS was captured by the mock provider"
    match = re.search(r"code: (\d{6})", msg.body)
    assert match, f"OTP not found in message body structure: {msg.body[:20]}..."
    return match.group(1)


def run_up_to_scan(client: TestClient, admin_headers: dict, agent: dict, agent_headers: dict) -> dict:
    """Helper: create return -> generate QR -> agent scans. Returns flow state."""
    ret = create_return(client, admin_headers, agent_id=agent["id"])
    qr = client.post(f"/api/returns/{ret['id']}/qr", headers=admin_headers)
    assert qr.status_code == 201, qr.text
    qr_data = qr.json()
    scan = client.post("/api/qr/scan", json={"token": qr_data["token"]}, headers=agent_headers)
    assert scan.status_code == 200, scan.text
    return {"return": ret, "qr": qr_data, "scan": scan.json()}


def run_full_flow_to_inspection(client: TestClient, admin_headers: dict, agent: dict,
                                agent_headers: dict, mock_sms: MockSMSProvider) -> dict:
    """Helper: full flow through OTP verification."""
    state = run_up_to_scan(client, admin_headers, agent, agent_headers)
    otp_req = client.post("/api/otp/request", json={}, headers={"Authorization": f"Bearer {state['scan']['scan_token']}"})
    assert otp_req.status_code == 200, otp_req.text
    code = extract_otp(mock_sms, agent["phone"])
    verify = client.post(
        "/api/otp/verify",
        json={"scan_token": state["scan"]["scan_token"], "code": code},
        headers=agent_headers,
    )
    assert verify.status_code == 200, verify.text
    state["verify"] = verify.json()
    return state


# ---------------------------------------------------------------------------
# Deterministic CV fakes (app-logic tests); live tests use the real engines.
# ---------------------------------------------------------------------------
def fake_ocr_ok(sku: str = "LAPTOP-X1-CARBON") -> OCRData:
    return OCRData(
        engine="fake-ocr", engine_version="test", status="OK",
        full_text=f"MODEL: {sku}\nThinkPad X1 Carbon",
        mean_confidence=92.5,
        blocks=[OCRBlock(text=f"MODEL: {sku}", confidence=92.5, box=[[0, 0], [10, 0], [10, 5], [0, 5]])],
        processing_ms=5,
    )


def fake_ocr_no_text() -> OCRData:
    return OCRData(engine="fake-ocr", engine_version="test", status="NO_TEXT_DETECTED", processing_ms=3)


def fake_ocr_unavailable() -> OCRData:
    return OCRData(engine="none", engine_version="", status="ENGINE_UNAVAILABLE", error="not installed")


def fake_detections_ok(labels: list[tuple[str, float]] | None = None) -> DetectionData:
    labels = labels if labels is not None else [("laptop", 0.91), ("laptop", 0.88)]
    items = [
        DetectionItem(class_id=i, class_label=lbl, confidence=conf,
                      bbox=[10.0 + i, 10.0, 100.0 + i, 80.0])
        for i, (lbl, conf) in enumerate(labels)
    ]
    return DetectionData(status="OK", model_name="fake.pt", model_path="fake.pt", device="cpu",
                         confidence_threshold=0.35, inference_ms=7, detections=items)


def fake_detections_unavailable() -> DetectionData:
    return DetectionData(status="MODEL_UNAVAILABLE", error="weights missing")


def fake_ai_ok(identity: str = "PASS", grade: str = "A_NEW", components: dict[str, bool] | None = None,
               confidence: float = 0.9, reasoning: str = "Matches the expected product in the photo.") -> AIData:
    comps = [
        {"name": name, "observed": obs, "note": "visible" if obs else "not visible"}
        for name, obs in (components or {}).items()
    ]
    return AIData(
        status="OK", provider="groq", model="fake-qwen", latency_ms=5, attempts=1,
        identity=identity, identity_reasoning=reasoning,
        condition_grade=grade, condition_reasoning="minor wear" if grade != "A_NEW" else "pristine",
        components=comps, visible_defects=[], confidence=confidence,
        payload={"identity": identity, "condition_grade": grade},
    )


def fake_ai_unavailable() -> AIData:
    return AIData(status="UNAVAILABLE", model="", error="GROQ_API_KEY is not configured")


@pytest.fixture()
def patch_fake_cv_ok(monkeypatch):
    from app.services import inspection_service, ocr_service, yolo_service

    monkeypatch.setattr(inspection_service, "ocr_service", ocr_service)
    monkeypatch.setattr(ocr_service, "run_ocr", lambda path: fake_ocr_ok())
    monkeypatch.setattr(yolo_service, "run_detection", lambda path: fake_detections_ok())


@pytest.fixture()
def patch_fake_ai_ok(monkeypatch):
    """AI stage returns a fully passing, schema-equivalent analysis."""
    from app.services import groq_service

    monkeypatch.setattr(
        groq_service,
        "run_ai_analysis",
        lambda ret, image_paths, ocr_texts, detections, view_types: fake_ai_ok(
            components={c.name: True for c in ret.expected_components}
        ),
    )


@pytest.fixture()
def patch_fake_ai_unavailable(monkeypatch):
    from app.services import groq_service

    monkeypatch.setattr(
        groq_service, "run_ai_analysis",
        lambda ret, image_paths, ocr_texts, detections, view_types: fake_ai_unavailable(),
    )


def image_bytes(width: int = 640, height: int = 480, fmt: str = "JPEG", color=(180, 180, 180)) -> bytes:
    from PIL import Image

    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def upload_image(client: TestClient, headers: dict, data: bytes, filename: str = "photo.jpg",
                 view_type: str = "STANDARD"):
    return client.post(
        "/api/inspections",
        files={"file": (filename, data, "image/jpeg")},
        data={"view_type": view_type},
        headers=headers,
    )
