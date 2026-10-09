"""Plan section 9 tests 13-14 (retake cap, override immutability) + the W7 event feed.

These need the service layer, so they run against a throwaway DB/media dir.
"""
import io

import pytest
from PIL import Image, ImageDraw

from agents.receiving import config, db, service
from shared.utils.hashing import verify


@pytest.fixture()
def agent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "receiving.db")
    monkeypatch.setattr(config, "MEDIA_DIR", tmp_path / "media")
    db.init_db()
    return tmp_path


def photo_bytes(with_barcode: bool = False, color=(196, 176, 150)) -> bytes:
    """A textured card-like image (edges matter: flat images read as blurry)."""
    img = Image.new("RGB", (900, 700), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 860, 660], outline=(90, 70, 50), width=6)
    draw.rectangle([120, 120, 420, 300], fill=(245, 245, 240))  # label area
    for x in range(140, 400, 18):  # barcode-ish bars (not a real code: must NOT decode)
        draw.rectangle([x, 160, x + 8, 260], fill=(20, 20, 20))
    draw.text((450, 400), "CARTON", fill=(40, 30, 20))
    if with_barcode:
        from barcode import Code128
        from barcode.writer import ImageWriter
        buf = io.BytesIO()
        Code128("08123456789012", writer=ImageWriter()).write(
            buf, options={"module_height": 5, "quiet_zone": 4})
        plate = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
        img.paste(plate, (140, 480))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()


def _line(org="org_demo_alpha"):
    return db.list_manifest(org)[0]


def test_13_retake_offered_once_then_final_quarantine(agent):
    line = _line()
    offered = service.start_scan(
        org_id="org_demo_alpha", line_id=line["id"], qty_received=line["qty_expected"],
        lot="", expiry="", operator="op_test",
        uploads=[("label", photo_bytes()), ("overall", photo_bytes())])
    assert offered["status"] == "pending_retake"
    assert offered["retake_offered"] is True and offered["coach"] is not None
    assert offered["verdict"] == "QUARANTINE"
    assert offered["record"]["status"] == "pending"

    # one retake, still bad -> FINAL, no second prompt (plan: retake cap = 1)
    final = service.do_retake(offered["rcv_id"], [("label", photo_bytes(color=(150, 140, 130)))])
    assert final["retake_offered"] is False and final["coach"] is None
    assert final["attempt"] == 1
    assert final["status"] == "final_open"          # QUARANTINE awaits review
    assert final["record"]["status"] == "completed"
    assert final["verdict"] == "QUARANTINE"

    # two records exist (offer + final); exactly one RECEIVING_FINAL event
    records = db.records_for(offered["rcv_id"])
    assert len(records) == 2
    finals = [e for e in db.list_events() if e["type"] == service.RECEIVING_FINAL
              and e["receiving_id"] == offered["rcv_id"]]
    assert len(finals) == 1


def test_14_override_never_mutates_the_original(agent):
    line = _line()
    scan = service.start_scan(
        org_id="org_demo_alpha", line_id=line["id"], qty_received=line["qty_expected"],
        lot="", expiry="", operator="op_test", uploads=[("label", photo_bytes())])
    service.do_finalize(scan["rcv_id"])     # skip the retake: finalize as-is

    stored = db.get_record(db.get_receiving(scan["rcv_id"])["effective_record_id"])
    before_decision = dict(stored["decision"])
    before_checks = list(stored["checks"])
    before_hash = stored["content_hash"]
    assert verify(stored)

    events_before = len([e for e in db.list_events() if e["type"] == service.RECEIVING_OVERRIDDEN])
    overridden = service.do_override(scan["rcv_id"], final_verdict="ACCEPT",
                                     reason_code="VISUAL_CHECK_OK", note="label creased in photo",
                                     operator="op_test")

    after = db.get_record(stored["record_id"])
    assert after["decision"] == before_decision, "the original verdict must be untouched"
    assert after["checks"] == before_checks, "an override must never rewrite the original check"
    assert after["content_hash"] == before_hash
    assert verify(after), "agent-level overrides sit outside the content hash"
    assert len(after["overrides"]) == 1
    assert after["overrides"][0]["original_verdict"] == before_decision["verdict"]
    assert after["overrides"][0]["new_verdict"] == "PASS"     # ACCEPT maps to PASS

    assert overridden["original_verdict"] == stored["payload"]["plan_verdict"]
    assert overridden["effective_verdict"] == "ACCEPT"
    assert db.get_receiving(scan["rcv_id"])["status"] == "final_closed"

    events = [e for e in db.list_events() if e["type"] == service.RECEIVING_OVERRIDDEN
              and e["receiving_id"] == scan["rcv_id"]]
    assert len(events) == 1, "exactly one RECEIVING_OVERRIDDEN event"
    assert events[0]["payload"]["reason_code"] == "VISUAL_CHECK_OK"
    assert len([e for e in db.list_events() if e["type"] == service.RECEIVING_FINAL
                and e["receiving_id"] == scan["rcv_id"]]) == 1


def test_retake_refused_after_finalize_and_wrong_tenant_is_refused(agent):
    line = _line()
    scan = service.start_scan(
        org_id="org_demo_alpha", line_id=line["id"], qty_received=line["qty_expected"],
        lot="", expiry="", operator="op_test", uploads=[("label", photo_bytes())])
    # a retake offer is not a judgment: overriding it must be refused until it is finished
    with pytest.raises(ValueError):
        service.do_override(scan["rcv_id"], final_verdict="ACCEPT",
                            reason_code="VISUAL_CHECK_OK", note="", operator="op_test")
    service.do_finalize(scan["rcv_id"])
    with pytest.raises(ValueError):
        service.do_retake(scan["rcv_id"], [("label", photo_bytes())])
    with pytest.raises(LookupError):
        service.start_scan(org_id="org_demo_bravo", line_id=line["id"], qty_received=1,
                           lot="", expiry="", operator="x",
                           uploads=[("label", photo_bytes())])
