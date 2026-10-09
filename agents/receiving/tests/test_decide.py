"""Plan section 9 tests 1-12 for decide(): the pure decision rules.

Test 13/14 (retake cap, override) live in test_flow.py because they need the
service layer; test 15 (explain) is in test_explain.py.
"""
from datetime import date

from agents.receiving import decide as D
from agents.receiving.config import DEFAULT_THRESHOLDS as TH

TODAY = date(2026, 10, 9)
GTIN = "4006381333931"
OTHER_GTIN = "4006381333932"

LINE = {"po_id": "PO-118", "line_no": 3, "gtin": GTIN, "qty_expected": 12,
        "lot": "L1", "expiry": ""}


def facts(*, barcode=True, gtin=GTIN, quality=None, damage=None):
    return {
        "barcode": {"found": barcode, "value": gtin if barcode else None, "photo_role": "label"},
        "quality": quality if quality is not None else [
            {"role": "label", "blur": 900.0, "glare": 0.01, "luminance": 130.0, "flags": []}],
        "damage": damage or {"damaged": False, "type": "none", "severity": 0,
                             "conf": 0.9, "description": "clean carton",
                             "source": "vlm", "model": "test", "prompt_version": "v1"},
    }


def run(**kw):
    args = dict(facts=FACTS_DEFAULT, line=LINE, qty_received=12, lot="L1", expiry="",
                thresholds=TH, today=TODAY, manifest_gtins={GTIN})
    args.update(kw)
    return D.decide(**args)


FACTS_DEFAULT = facts()


def damaged(severity, conf=0.9, source="vlm", kind="crush"):
    return facts(damage={"damaged": severity > 0, "type": kind, "severity": severity,
                         "conf": conf, "description": "staged", "source": source,
                         "model": "test", "prompt_version": "v1"})


def test_1_clean_passes():
    r = run()
    assert r["verdict"] == D.ACCEPT and r["reasons"] == [] and r["retakeable"] is False


def test_2_severe_damage_rejects():
    r = run(facts=damaged(5, 0.9))
    assert r["verdict"] == D.REJECT and r["reasons"] == [D.SEVERE_DAMAGE]
    assert r["retakeable"] is False


def test_3_severe_damage_not_downgraded_by_image_problems():
    f = damaged(5, 0.9)
    f["barcode"] = {"found": False, "value": None, "photo_role": "label"}
    f["quality"] = [{"role": "label", "blur": 40.0, "glare": 0.3, "luminance": 120.0,
                     "flags": ["IMG_GLARE"]}]
    r = run(facts=f, manifest_gtins=set())
    assert r["verdict"] == D.REJECT and D.SEVERE_DAMAGE in r["reasons"]
    assert D.NO_BARCODE in r["reasons"] and D.IMG_GLARE in r["reasons"]


def test_4_expired_rejects():
    r = run(line={**LINE, "expiry": "2026-10-08"})
    assert r["verdict"] == D.REJECT and r["reasons"] == [D.EXPIRED]


def test_5_barcode_not_in_manifest_escalates():
    r = run(facts=facts(gtin="9999999999999"), manifest_gtins={GTIN, OTHER_GTIN})
    assert r["verdict"] == D.ESCALATE and r["reasons"] == [D.NOT_IN_MANIFEST]


def test_6_barcode_on_other_line_escalates():
    r = run(facts=facts(gtin=OTHER_GTIN), manifest_gtins={GTIN, OTHER_GTIN})
    assert r["verdict"] == D.ESCALATE and r["reasons"] == [D.WRONG_SKU]


def test_7_qty_mismatch_escalates():
    r = run(qty_received=8)
    assert r["verdict"] == D.ESCALATE and r["reasons"] == [D.QTY_MISMATCH]


def test_8_lot_conflict_only_when_both_present():
    assert D.LOT_CONFLICT in run(lot="L2")["reasons"]
    assert D.LOT_CONFLICT not in run(lot="")["reasons"]
    assert D.LOT_CONFLICT not in run(lot="", line={**LINE, "lot": ""})["reasons"]


def test_9_moderate_damage_quarantines_not_retakeable():
    r = run(facts=damaged(3, 0.9))
    assert r["verdict"] == D.QUARANTINE and r["reasons"] == [D.MODERATE_DAMAGE]
    assert r["retakeable"] is False


def test_10_no_barcode_with_blurry_label_is_retakeable():
    f = facts(barcode=False)
    f["quality"] = [{"role": "label", "blur": 40.0, "glare": 0.01, "luminance": 130.0,
                     "flags": ["IMG_BLURRY"]}]
    r = run(facts=f, manifest_gtins=set())
    assert r["verdict"] == D.QUARANTINE
    assert r["reasons"] == [D.NO_BARCODE, D.IMG_BLURRY] or r["reasons"] == [D.IMG_BLURRY, D.NO_BARCODE]
    assert D.NO_BARCODE in r["reasons"] and D.IMG_BLURRY in r["reasons"]
    assert r["retakeable"] is True


def test_11_glare_alone_never_changes_the_verdict():
    f = facts()
    f["quality"] = [{"role": "label", "blur": 900.0, "glare": 0.5, "luminance": 130.0,
                     "flags": ["IMG_GLARE"]}]
    r = run(facts=f)
    assert r["verdict"] == D.ACCEPT and r["reasons"] == []


def test_12_vlm_unavailable_fails_safe_to_quarantine():
    r = run(facts=damaged(5, 0.0, source="unavailable"))
    assert r["verdict"] == D.QUARANTINE and r["reasons"] == [D.LOW_CONF_DAMAGE]
    assert r["retakeable"] is True
    # even a "severe" reading must not be trusted below the confidence threshold
    r2 = run(facts=damaged(5, 0.4))
    assert r2["verdict"] == D.QUARANTINE and r2["reasons"] == [D.LOW_CONF_DAMAGE]


def test_contract_view_covers_all_four_states():
    for state in (D.ACCEPT, D.QUARANTINE, D.ESCALATE, D.REJECT):
        verdict, outcome, next_step = D.contract_view(state)
        assert verdict in ("PASS", "FAIL", "UNCERTAIN")
        assert outcome in ("accept", "accept_with_exceptions", "reject", "pending_review")
        assert next_step in ("continue", "review", "retry", "stop", "route_to_recovery", "complete")
