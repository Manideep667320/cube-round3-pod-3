"""Challenge-alignment evaluation suite (15 labeled scenarios).

Each scenario drives the REAL evidence builder and REAL decision engine with
deterministic OCR/YOLO/AI inputs and asserts the expected dimension outcomes.
This measures decision-logic correctness against ground truth labels; model
accuracy itself is measured separately by live tests (live_cv, groq_live)
because no labeled real-photo dataset is available in this environment - see
docs/GAP_ANALYSIS.md.
"""
from __future__ import annotations

import pytest

from agents.returns.backend.app.models import ExpectedComponent, ReturnRecord
from agents.returns.backend.app.services.decision_service import decide
from agents.returns.backend.app.services.evidence_service import build_evidence
from agents.returns.backend.app.services.groq_service import AIData
from agents.returns.backend.app.services.ocr_service import OCRData
from agents.returns.backend.app.services.yolo_service import DetectionData, DetectionItem

COMPONENTS = ("headphones", "case", "cable", "manual")


def _ret(components=COMPONENTS, sku="HP-X100") -> ReturnRecord:
    ret = ReturnRecord(return_code="RG-EVAL", order_reference="o", expected_sku=sku, created_by_id="x")
    ret.expected_components = [ExpectedComponent(name=c, yolo_class_hints=c) for c in components]
    return ret


def _ocr(text="MODEL: HP-X100", status="OK", conf=92.0) -> OCRData:
    return OCRData(engine="t", engine_version="1", status=status, full_text=text,
                   mean_confidence=conf if status == "OK" else None, blocks=[])


def _yolo(labels=(), status="OK") -> DetectionData:
    return DetectionData(status=status, model_name="m.pt", confidence_threshold=0.35, inference_ms=1,
                         detections=[DetectionItem(i, l, 0.9, [1, 1, 10, 10]) for i, l in enumerate(labels)])


def _ai(identity="PASS", grade="A_NEW", observed=COMPONENTS, conf=0.9) -> AIData:
    return AIData(status="OK", provider="groq", model="eval-fake", latency_ms=1,
                  identity=identity, identity_reasoning="eval", condition_grade=grade,
                  condition_reasoning="eval",
                  components=[{"name": n, "observed": n in observed, "note": ""} for n in COMPONENTS],
                  visible_defects=[], confidence=conf, payload={})


def _run(payloads):
    return decide(payloads)


# 1. Correct returned product, all components, new-looking
def test_scenario_01_correct_product():
    r = _run([build_evidence(_ret(), _ocr(), _yolo(), _ai())])
    assert r.outcome == "APPROVE" and r.disposition == "RESTOCK"


# 2. Wrong returned product (conflicting high-confidence label)
def test_scenario_02_wrong_product():
    r = _run([build_evidence(_ret(), _ocr(text="MODEL: TOTALLY-DIFF-9"), _yolo(), _ai())])
    assert r.outcome == "REJECT" and r.disposition is None


# 3. Two similar-looking variants: OCR unreadable, AI uncertain
def test_scenario_03_similar_variants():
    payload = build_evidence(_ret(), _ocr(text="", status="NO_TEXT_DETECTED"), _yolo(),
                             _ai(identity="UNCERTAIN", conf=0.5))
    r = _run([payload])
    assert r.outcome == "MANUAL_REVIEW" and r.disposition == "RESTOCK"  # tentative rec only


# 4. One missing accessory (layout photo)
def test_scenario_04_one_missing():
    a = build_evidence(_ret(), _ocr(), _yolo(), _ai(observed=("headphones", "case", "manual")))
    b = build_evidence(_ret(), _ocr(), _yolo(),
                       _ai(observed=("headphones", "case", "manual")), view_type="CONTENTS_LAYOUT")
    r = _run([a, b])
    assert r.outcome == "MANUAL_REVIEW"
    assert r.disposition == "REFURBISH"
    assert any("cable" in x["explanation"] and "Confirmed missing" in x["explanation"] for x in r.rationale)


# 5. Multiple missing accessories
def test_scenario_05_multiple_missing():
    a = build_evidence(_ret(), _ocr(), _yolo(), _ai(observed=("headphones",)), view_type="CONTENTS_LAYOUT")
    r = _run([a])
    text = " ".join(x["explanation"] for x in r.rationale)
    assert "cable" in text and "case" in text and "Confirmed missing" in text
    assert r.outcome == "MANUAL_REVIEW"


# 6. All expected components present
def test_scenario_06_all_present():
    r = _run([build_evidence(_ret(), _ocr(), _yolo(), _ai())])
    assert r.outcome == "APPROVE"


# 7. New-looking product
def test_scenario_07_new():
    r = _run([build_evidence(_ret(), _ocr(), _yolo(), _ai(grade="A_NEW"))])
    assert r.disposition == "RESTOCK" and r.outcome == "APPROVE"


# 8. Lightly used product
def test_scenario_08_lightly_used():
    r = _run([build_evidence(_ret(), _ocr(), _yolo(), _ai(grade="B_LIGHT"))])
    assert r.disposition == "RESTOCK" and r.outcome == "APPROVE"


# 9. Visibly damaged product
def test_scenario_09_damaged():
    r = _run([build_evidence(_ret(), _ocr(), _yolo(), _ai(grade="D_DAMAGED"))])
    assert r.disposition == "LIQUIDATE"
    assert r.outcome == "MANUAL_REVIEW"  # liquidation requires human sign-off


# 10. Heavily damaged / non-functional
def test_scenario_10_destroyed():
    r = _run([build_evidence(_ret(), _ocr(), _yolo(), _ai(grade="E_NON_FUNCTIONAL"))])
    assert r.disposition == "DISPOSE"
    assert r.outcome == "MANUAL_REVIEW"


# 11. Ambiguous condition
def test_scenario_11_ambiguous_condition():
    r = _run([build_evidence(_ret(), _ocr(), _yolo(), _ai(grade="UNKNOWN"))])
    assert r.outcome == "MANUAL_REVIEW" and r.disposition is None


# 12. Blurry / unreadable label
def test_scenario_12_blurry_label():
    payload = build_evidence(_ret(), _ocr(text="### ???", status="LOW_CONFIDENCE", conf=30.0), _yolo(),
                             _ai(identity="UNCERTAIN", conf=0.4))
    assert payload["identity"]["verdict"] == "UNCERTAIN"
    r = _run([payload])
    assert r.outcome == "MANUAL_REVIEW"


# 13. Conflicting OCR and visual findings
def test_scenario_13_conflicting_sources():
    # OCR shows a conflicting SKU; AI leans PASS -> strong OCR conflict still FAILs.
    payload = build_evidence(_ret(), _ocr(text="MODEL: OTHERCO-77"), _yolo(), _ai(identity="PASS"))
    assert payload["identity"]["verdict"] == "FAIL"
    assert _run([payload]).outcome == "REJECT"


# 14. Accessory hidden outside camera view (no layout photo)
def test_scenario_14_hidden_accessory():
    # The manual is genuinely in the box but outside the camera frame: neither
    # the detector nor the AI can see it, and there is no layout photo.
    payload = build_evidence(_ret(), _ocr(), _yolo(),
                             _ai(observed=("headphones", "case", "cable")))
    comp = {c["name"]: c["observation"] for c in payload["components"]}
    assert comp["manual"] in ("NOT_OBSERVED", "UNCERTAIN")
    r = _run([payload])
    assert r.outcome == "MANUAL_REVIEW"
    # Never claimed missing without a layout view.
    assert not any("Confirmed missing" in x["explanation"] for x in r.rationale)


# 15. Missing model weights / inference failure
def test_scenario_15_model_unavailable():
    payload = build_evidence(_ret(), _ocr(), _yolo(status="MODEL_UNAVAILABLE"),
                             AIData(status="FAILED", error="weights missing"))
    r = _run([payload])
    assert r.outcome == "MANUAL_REVIEW"
    text = " ".join(x["explanation"] for x in r.rationale)
    assert "Object-detection evidence unavailable" in text
    assert "AI visual analysis" in text
