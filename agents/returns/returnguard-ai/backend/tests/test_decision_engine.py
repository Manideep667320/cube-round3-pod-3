"""Decision engine v2 unit tests (pure functions over evidence payloads).

These use the REAL evidence builder and REAL decision engine with deterministic
OCR/YOLO/AI inputs - only the external engines are stubbed.
"""
from __future__ import annotations

from app.models import ExpectedComponent, ReturnRecord
from app.services.decision_service import decide
from app.services.evidence_service import build_evidence
from app.services.groq_service import AIData
from app.services.ocr_service import OCRData
from app.services.yolo_service import DetectionData, DetectionItem


def _ret(sku="SKU-12345", components=("laptop", "charger")) -> ReturnRecord:
    ret = ReturnRecord(return_code="RG-TEST", order_reference="o", expected_sku=sku, created_by_id="x")
    ret.expected_components = [ExpectedComponent(name=c, yolo_class_hints=c) for c in components]
    return ret


def _ocr(sku="SKU-12345", status="OK", text=None, conf=92.0) -> OCRData:
    body = text if text is not None else f"MODEL: {sku}"
    return OCRData(engine="t", engine_version="1", status=status, full_text=body,
                   mean_confidence=conf if status == "OK" else None, blocks=[])


def _yolo(labels=("laptop",), status="OK") -> DetectionData:
    items = [DetectionItem(i, lbl, 0.9, [1, 1, 50, 50]) for i, lbl in enumerate(labels)]
    return DetectionData(status=status, model_name="m.pt", confidence_threshold=0.35,
                         inference_ms=1, detections=items)


def _ai(identity="PASS", grade="A_NEW", observed=("laptop", "charger"), conf=0.92) -> AIData:
    return AIData(status="OK", provider="groq", model="qwen-test", latency_ms=3,
                  identity=identity, identity_reasoning="test", condition_grade=grade,
                  condition_reasoning="test",
                  components=[{"name": n, "observed": n in observed, "note": ""} for n in ("laptop", "charger")],
                  visible_defects=[], confidence=conf, payload={})


def _ai_down() -> AIData:
    return AIData(status="UNAVAILABLE", error="no key")


# ---------------------------------------------------------------------------
# Full-pass scenarios
# ---------------------------------------------------------------------------
def test_approve_when_all_dimensions_pass():
    payload = build_evidence(_ret(), _ocr(), _yolo(), _ai())
    assert payload["identity"]["verdict"] == "PASS"
    assert payload["condition"]["grade"] == "A_NEW"
    result = decide([payload])
    assert result.outcome == "APPROVE"
    assert result.disposition == "RESTOCK"


def test_ai_only_identity_is_uncertain_not_pass():
    # No readable SKU -> identity cannot PASS even when the model agrees.
    payload = build_evidence(_ret(), _ocr(text="no label here", status="OK"), _yolo(), _ai())
    assert payload["identity"]["verdict"] == "UNCERTAIN"
    assert decide([payload]).outcome == "MANUAL_REVIEW"


def test_ocr_only_identity_is_uncertain():
    # AI down: readable SKU alone is not proof of the physical product.
    payload = build_evidence(_ret(), _ocr(), _yolo(), _ai_down())
    assert payload["identity"]["verdict"] == "UNCERTAIN"
    assert decide([payload]).outcome == "MANUAL_REVIEW"


# ---------------------------------------------------------------------------
# Identity failure
# ---------------------------------------------------------------------------
def test_conflicting_label_rejects():
    payload = build_evidence(_ret(), _ocr(text="MODEL: SKU-99999"), _yolo(), _ai())
    assert payload["identity"]["verdict"] == "FAIL"
    result = decide([payload])
    assert result.outcome == "REJECT"
    assert result.disposition is None  # withheld on identity failure


def test_high_confidence_ai_fail_is_identity_fail():
    payload = build_evidence(_ret(), _ocr(text="unreadable smudge"), _yolo(), _ai(identity="FAIL", conf=0.9))
    assert payload["identity"]["verdict"] == "FAIL"
    assert decide([payload]).outcome == "REJECT"


def test_low_confidence_ai_fail_stays_uncertain():
    payload = build_evidence(_ret(), _ocr(status="NO_TEXT_DETECTED", text=""), _yolo(), _ai(identity="FAIL", conf=0.5))
    assert payload["identity"]["verdict"] == "UNCERTAIN"


# ---------------------------------------------------------------------------
# Completeness across photos
# ---------------------------------------------------------------------------
def test_single_standard_photo_never_confirms_missing():
    payload = build_evidence(_ret(), _ocr(), _yolo(labels=("laptop",)), _ai(observed=("laptop",)))
    comp = {c["name"]: c["observation"] for c in payload["components"]}
    assert comp["laptop"] == "OBSERVED"
    assert comp["charger"] in ("NOT_OBSERVED", "UNCERTAIN")
    result = decide([payload])
    assert result.outcome == "MANUAL_REVIEW"
    # Nothing is claimed missing.
    assert all(r["rule_id"] != "CMP-03" for r in result.rationale)


def test_contents_layout_confirms_missing():
    standard = build_evidence(_ret(), _ocr(), _yolo(labels=("laptop",)), _ai(observed=("laptop",)))
    layout = build_evidence(_ret(), _ocr(), _yolo(labels=("laptop",)),
                            _ai(observed=("laptop",)), view_type="CONTENTS_LAYOUT")
    result = decide([standard, layout])
    assert result.outcome == "MANUAL_REVIEW"  # reviewer confirms disposition
    missing_rules = [r for r in result.rationale if "Confirmed missing" in r["explanation"]]
    assert missing_rules and "charger" in missing_rules[0]["explanation"]
    # RESTOCK would be downgraded to REFURBISH by the missing accessory.
    assert result.disposition == "REFURBISH"


def test_component_observed_in_any_photo_passes():
    first = build_evidence(_ret(), _ocr(), _yolo(labels=("laptop",)), _ai(observed=("laptop",)))
    second = build_evidence(_ret(), _ocr(), _yolo(labels=("laptop", "charger")),
                            _ai(observed=("laptop", "charger")))
    result = decide([first, second])
    assert result.outcome == "APPROVE"


# ---------------------------------------------------------------------------
# Condition grades and dispositions
# ---------------------------------------------------------------------------
def test_worst_grade_wins_across_photos():
    a = build_evidence(_ret(), _ocr(), _yolo(), _ai(grade="A_NEW"))
    c = build_evidence(_ret(), _ocr(), _yolo(), _ai(grade="C_MODERATE"))
    result = decide([a, c])
    assert result.disposition == "REFURBISH"


def test_unknown_condition_blocks_approval_and_disposition():
    payload = build_evidence(_ret(), _ocr(), _yolo(), _ai_down())
    assert payload["condition"]["grade"] == "UNKNOWN"
    result = decide([payload])
    assert result.outcome == "MANUAL_REVIEW"
    assert result.disposition is None


def test_damaged_grade_liquidates_but_never_auto_approves():
    payload = build_evidence(_ret(), _ocr(), _yolo(), _ai(grade="D_DAMAGED"))
    result = decide([payload])
    assert result.disposition == "LIQUIDATE"
    # Even with all dimensions passing, liquidation needs human sign-off.
    assert result.outcome == "MANUAL_REVIEW"


def test_ai_failure_blocks_auto_approval():
    payload = build_evidence(_ret(), _ocr(), _yolo(), AIData(status="MALFORMED", error="bad json"))
    result = decide([payload])
    assert result.outcome == "MANUAL_REVIEW"
    assert any(r["rule_id"] == "AI-01" for r in result.rationale)


def test_no_evidence_routes_to_review():
    result = decide([])
    assert result.outcome == "MANUAL_REVIEW"
    assert result.disposition is None


def test_rationale_is_persistable_and_explainable():
    payload = build_evidence(_ret(), _ocr(), _yolo(), _ai())
    result = decide([payload])
    assert result.rationale
    for r in result.rationale:
        assert set(r) == {"rule_id", "outcome", "explanation"}
        assert r["explanation"]
