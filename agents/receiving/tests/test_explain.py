"""Plan section 9 test 15 (explain: no unresolved placeholders) + the coach table (W4)."""
from datetime import date

from agents.receiving import coach as C
from agents.receiving import decide as D
from agents.receiving import explain as E
from agents.receiving.config import DEFAULT_THRESHOLDS as TH

TODAY = date(2026, 10, 9)
LINE = {"po_id": "PO-118", "line_no": 3, "gtin": "4006381333931", "qty_expected": 12,
        "lot": "L1", "expiry": "2026-01-01"}


def facts(damage=None, quality=None, barcode=True, value="4006381333931"):
    return {
        "barcode": {"found": barcode, "value": value if barcode else None, "photo_role": "label"},
        "quality": quality or [{"role": "label", "blur": 40.0, "glare": 0.3,
                                "luminance": 120.0, "flags": ["IMG_GLARE"]}],
        "damage": damage or {"damaged": False, "type": "none", "severity": 0, "conf": 0.2,
                             "description": "", "source": "unavailable", "model": "",
                             "prompt_version": "v1"},
    }


def explain_all():
    """One output per reason code, covering every template in TEMPLATES."""
    quality = [{"role": "label", "blur": 40.0, "glare": 0.3, "luminance": 10.0,
                "flags": ["IMG_BLURRY", "IMG_GLARE", "IMG_DARK"]}]
    f = facts(damage={"damaged": True, "type": "crush", "severity": 5, "conf": 0.9,
                      "description": "", "source": "vlm", "model": "m", "prompt_version": "v1"},
              quality=quality, barcode=True, value="9999999999999")
    # every code at once: decide() would not raise them all together, but explain()
    # must be able to render any code it is handed.
    reasons = list(D.REASON_ORDER)
    return E.explain(reasons, facts=f, line=LINE, qty_received=8, lot="L2",
                     expiry="2026-01-01", thresholds=TH, today=TODAY, photo_count=3)


def test_15_explain_leaves_no_unresolved_placeholders():
    lines = explain_all()
    assert {ln["code"] for ln in lines} == set(D.REASON_CODES)
    for ln in lines:
        assert "{" not in ln["text"] and "}" not in ln["text"], ln
        assert ln["text"].strip(), ln


def test_explain_interpolates_real_numbers():
    f = facts(damage={"damaged": True, "type": "crush", "severity": 5, "conf": 0.9,
                      "description": "", "source": "vlm", "model": "m", "prompt_version": "v1"})
    [line] = E.explain([D.SEVERE_DAMAGE], facts=f, line=LINE, qty_received=8, lot="",
                       expiry="", thresholds=TH, today=TODAY, photo_count=1)
    assert "severity 5/5" in line["text"] and "0.90" in line["text"]


def test_coach_priority_and_roles():
    facts_ = facts(quality=[{"role": "closeup", "blur": 30.0, "glare": 0.0,
                             "luminance": 130.0, "flags": ["IMG_BLURRY"]}])
    # a specific image fix beats the generic no-barcode hint
    out = C.coach([D.NO_BARCODE, D.IMG_BLURRY], facts_)
    assert out["reason"] == D.IMG_BLURRY and out["photo_role"] == "closeup"
    assert "focus" in out["instruction"]

    assert C.coach([D.NO_BARCODE], facts(barcode=False))["photo_role"] == "label"
    assert C.coach([D.LOW_CONF_DAMAGE])["photo_role"] == "closeup"
    assert C.coach([D.MODERATE_DAMAGE]) is None      # not retakeable, no coach
    assert C.coach([D.QTY_MISMATCH]) is None
    assert C.coach([]) is None


def test_coach_glare_and_dark_wording():
    glare = C.coach([D.IMG_GLARE], facts())
    assert "Tilt" in glare["instruction"] and glare["photo_role"] == "label"
    dark_facts = facts(quality=[{"role": "label", "blur": 900.0, "glare": 0.0,
                                 "luminance": 10.0, "flags": ["IMG_DARK"]}])
    dark = C.coach([D.IMG_DARK], dark_facts)
    assert "light" in dark["instruction"]
