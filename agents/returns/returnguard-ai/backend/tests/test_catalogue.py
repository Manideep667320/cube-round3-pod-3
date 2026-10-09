"""Product catalogue API tests."""
from __future__ import annotations

import uuid

from tests.conftest import make_agent


def _create_catalogue(client, admin_headers, sku=None, name="Wireless Headphones X100"):
    sku = sku or f"HEADPHONES-{uuid.uuid4().hex[:6].upper()}"
    return client.post(
        "/api/catalogue",
        json={
            "sku": sku,
            "name": name,
            "description": "Over-ear wireless headphones",
            "default_components": [
                {"name": "headphones", "yolo_class_hints": ["headphones"], "ocr_text_hint": ""},
                {"name": "carrying case", "yolo_class_hints": ["case"], "ocr_text_hint": ""},
                {"name": "usb cable", "yolo_class_hints": ["usb cable"], "ocr_text_hint": ""},
                {"name": "manual", "yolo_class_hints": [], "ocr_text_hint": "user guide"},
            ],
            "identifying_features": ["foldable ear cups", "brand logo on headband"],
        },
        headers=admin_headers,
    )


def test_admin_creates_catalogue_entry(client, admin_headers):
    resp = _create_catalogue(client, admin_headers, sku=f"HDP-{uuid.uuid4().hex[:6].upper()}")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["sku"].startswith("HDP-")
    assert len(body["default_components"]) == 4
    assert "brand logo on headband" in body["identifying_features"]


def test_duplicate_sku_rejected(client, admin_headers):
    sku = f"DUP-{uuid.uuid4().hex[:6].upper()}"
    assert _create_catalogue(client, admin_headers, sku=sku).status_code == 201
    assert _create_catalogue(client, admin_headers, sku=sku).status_code == 409


def test_agents_cannot_manage_catalogue(client, admin_headers, agent_headers):
    resp = client.post(
        "/api/catalogue",
        json={"sku": "X-1", "name": "x"},
        headers=agent_headers,
    )
    assert resp.status_code == 403
    assert client.get("/api/catalogue", headers=agent_headers).status_code == 200  # read is allowed


def test_unauthenticated_cannot_read_catalogue(client):
    assert client.get("/api/catalogue").status_code == 401


def test_return_created_from_catalogue_uses_default_components(client, admin_headers, agent):
    product = _create_catalogue(client, admin_headers, sku=f"RET-{uuid.uuid4().hex[:6].upper()}").json()
    resp = client.post(
        "/api/returns",
        json={
            "order_reference": "ORD-CAT-1",
            "expected_sku": "HEADPHONES-X100",
            "product_description": "",
            "catalogue_product_id": product["id"],
            "assigned_agent_id": agent["id"],
            "expected_components": [],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["catalogue_product_id"] == product["id"]
    names = [c["name"] for c in body["expected_components"]]
    assert names == ["headphones", "carrying case", "usb cable", "manual"]


def test_invalid_catalogue_reference_rejected(client, admin_headers, agent):
    resp = client.post(
        "/api/returns",
        json={
            "order_reference": "ORD-CAT-2",
            "expected_sku": "SOME-SKU",
            "catalogue_product_id": "00000000-0000-0000-0000-000000000000",
            "assigned_agent_id": agent["id"],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_catalogue"


def test_operator_can_be_assigned(client, admin_headers):
    operator = make_agent(client, admin_headers, username="operator_one", phone="+15550000010")
    # make_agent creates AGENT role; create an operator explicitly.
    resp = client.post(
        "/api/admin/users",
        json={"username": "warehouse-op", "password": "op-pass-12345", "role": "OPERATOR",
              "phone": "+15550000011", "phone_verified": True},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    op_id = resp.json()["id"]
    ret = client.post(
        "/api/returns",
        json={"order_reference": "ORD-OP-1", "expected_sku": "SKU-OP",
              "assigned_agent_id": op_id, "expected_components": []},
        headers=admin_headers,
    )
    assert ret.status_code == 201
    assert ret.json()["assigned_agent_id"] == op_id
    assert operator  # agent still assignable too
