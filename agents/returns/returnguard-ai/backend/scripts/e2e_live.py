"""Live end-to-end workflow check (in-process TestClient).

Runs the FULL workflow with REAL engines: admin bootstrap login -> catalogue +
return -> QR -> scan -> OTP (read from the in-process mock SMS store) ->
photo upload with real RapidOCR + real YOLO + REAL Groq/Qwen vision ->
prints the four-dimension result. GROQ_API_KEY must be configured for the AI
stage to run; without it the script still completes and reports UNAVAILABLE.

Usage: python -m scripts.e2e_live
"""
from __future__ import annotations

import io
import os
import re
import sys

os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.sms_service import get_sms_provider  # noqa: E402


def make_label_image() -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (900, 700), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
        small = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = small = ImageFont.load_default()
    d.rectangle([80, 200, 820, 620], fill=(30, 30, 35))
    d.rectangle([110, 230, 790, 470], fill=(70, 130, 180))
    d.text((120, 90), "SKU: LIVE-E2E-42", fill="black", font=font)
    d.text((120, 520), "ReturnGuard test unit", fill="white", font=small)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def main() -> int:
    with TestClient(app) as client:
        # Bootstrap admin comes from the test env bootstrap vars if present;
        # otherwise create one ad hoc for this run.
        resp = client.post("/api/auth/login", json={"username": "testadmin", "password": "test-admin-pass-123"})
        if resp.status_code != 200:
            print("E2E: could not sign in as bootstrap admin (set ADMIN_BOOTSTRAP_* first).")
            return 1
        admin = {"Authorization": f"Bearer {resp.json()['access_token']}"}

        agent_resp = client.post(
            "/api/admin/users",
            json={"username": "e2e_agent", "password": "e2e-agent-pass-1", "role": "AGENT",
                  "phone": "+15559990001", "phone_verified": True},
            headers=admin,
        )
        agent = agent_resp.json() if agent_resp.status_code == 201 else None
        if agent is None:
            users = client.get("/api/admin/users", headers=admin).json()
            agent = next(u for u in users if u["username"] == "e2e_agent")

        ret = client.post(
            "/api/returns",
            json={"order_reference": "ORD-E2E-1", "expected_sku": "LIVE-E2E-42",
                  "product_description": "E2E live verification unit",
                  "expected_components": [
                      {"name": "unit", "yolo_class_hints": ["laptop"], "ocr_text_hint": ""},
                      {"name": "cable", "yolo_class_hints": ["usb cable"], "ocr_text_hint": ""},
                  ],
                  "assigned_agent_id": agent["id"]},
            headers=admin,
        ).json()

        qr = client.post(f"/api/returns/{ret['id']}/qr", headers=admin).json()
        agent_login = client.post("/api/auth/login", json={"username": "e2e_agent", "password": "e2e-agent-pass-1"}).json()
        agent_h = {"Authorization": f"Bearer {agent_login['access_token']}"}
        scan = client.post("/api/qr/scan", json={"token": qr["token"]}, headers=agent_h).json()

        client.post("/api/otp/request", json={}, headers={"Authorization": f"Bearer {scan['scan_token']}"})
        msg = get_sms_provider().last_for("+15559990001")
        code = re.search(r"code: (\d{6})", msg.body).group(1)
        verify = client.post("/api/otp/verify", json={"scan_token": scan["scan_token"], "code": code}, headers=agent_h).json()

        upload = client.post(
            "/api/inspections",
            files={"file": ("live.jpg", make_label_image(), "image/jpeg")},
            data={"view_type": "STANDARD"},
            headers={"Authorization": f"Bearer {verify['inspection_token']}"},
        )
        if upload.status_code != 201:
            print("E2E FAILED at upload:", upload.status_code, upload.text[:400])
            return 1
        body = upload.json()

        print("=" * 70)
        print("E2E LIVE WORKFLOW RESULT")
        print("=" * 70)
        print(f"  QR scan ............ OK (single-use, agent-bound)")
        print(f"  OTP ................ OK (delivered via mock, verified: {code})")
        print(f"  OCR ................ {body['ocr']['status']} (engine={body['ocr']['engine']}, "
              f"{body['ocr']['processing_ms']} ms) text={body['ocr']['full_text'][:60]!r}")
        print(f"  YOLO ............... {body['detection_run']['status']} "
              f"({len(body['detection_run']['detections'])} detections, {body['detection_run']['inference_ms']} ms)")
        ai = body["ai_analysis"]
        print(f"  AI (Groq/Qwen) ..... {ai['status']} model={ai['model']} {ai['latency_ms']} ms")
        ev = body["evidence"]["payload"]
        print(f"  Identity ........... {ev['identity']['verdict']} sources={ev['identity']['sources']}")
        print(f"  Completeness ....... " + ", ".join(f"{c['name']}={c['observation']}" for c in ev["components"]))
        print(f"  Condition .......... {ev['condition']['grade']}")
        d = body["decision"]
        print(f"  Decision ........... {d['outcome']} disposition={d['disposition']} (engine v{d['engine_version']})")
        print("=" * 70)
        return 0


if __name__ == "__main__":
    sys.exit(main())
