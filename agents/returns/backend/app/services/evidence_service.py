"""Structured evidence builder (schema v2).

Builds PER-PHOTO evidence from real OCR, real YOLO inference and the (optional)
validated Groq/Qwen visual-reasoning output:

    identity     : PASS / FAIL / UNCERTAIN with the sources that support it
    components   : per expected component: OBSERVED / NOT_OBSERVED / UNCERTAIN
                   (CONFIRMED_MISSING is decided at RETURN level, never here -
                   a single standard photo can't establish absence)
    condition    : grade from the configured condition scale (AI-assessed) or
                   UNKNOWN; visible defects listed verbatim from the model
    ocr_summary / yolo_summary / ai_summary : engine metadata + honest statuses
    uncertainties: explicit open questions for the reviewer

Policy: the AI model's output is validated EVIDENCE, not authority. A component
the AI claims to see but the detector did not corroborate is downgraded to
UNCERTAIN unless the model's overall confidence is high; OCR text alone never
establishes identity.
"""
from __future__ import annotations

import re

from agents.returns.backend.app.models import ExpectedComponent, ReturnRecord
from agents.returns.backend.app.services.ocr_service import OCRData
from agents.returns.backend.app.services.yolo_service import DetectionData

EVIDENCE_SCHEMA_VERSION = "2.0"

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Minimum AI confidence for an uncorroborated AI component sighting to count.
AI_COMPONENT_CONFIDENCE_FLOOR = 0.7
# Minimum AI confidence for an AI identity FAIL to count as strong evidence.
AI_IDENTITY_FAIL_FLOOR = 0.8


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _match_component_yolo(component: ExpectedComponent, yolo: DetectionData) -> list[dict]:
    hints = [h.strip().lower() for h in (component.yolo_class_hints or "").split(",") if h.strip()]
    hint_tokens: set[str] = set()
    for h in hints:
        hint_tokens |= _tokens(h)
    hint_tokens |= _tokens(component.name)
    matched = []
    if yolo.status == "OK":
        for det in yolo.detections:
            label_tokens = _tokens(det.class_label)
            if label_tokens & hint_tokens:
                matched.append({"class_label": det.class_label, "confidence": det.confidence, "bbox": det.bbox})
    return matched


def _component_observation(component: ExpectedComponent, yolo: DetectionData, ai) -> dict:
    matched = _match_component_yolo(component, yolo)
    if matched:
        return {
            "name": component.name,
            "observation": "OBSERVED",
            "evidence_sources": ["yolo"],
            "matched_detections": matched,
            "note": "Supported by object-detection evidence in this photo.",
        }

    # AI-only sighting: corroborate via model confidence (validated evidence,
    # never authority on its own at low confidence).
    if ai is not None and ai.status == "OK":
        ai_finding = next(
            (c for c in ai.components if c["name"].strip().lower() == component.name.strip().lower()), None
        )
        if ai_finding is not None and ai_finding["observed"]:
            if (ai.confidence or 0) >= AI_COMPONENT_CONFIDENCE_FLOOR:
                return {
                    "name": component.name,
                    "observation": "OBSERVED",
                    "evidence_sources": ["ai"],
                    "matched_detections": [],
                    "note": f"Reported visible by {ai.provider}/{ai.model} "
                            f"(confidence {ai.confidence}); not corroborated by the detector.",
                }
            return {
                "name": component.name,
                "observation": "UNCERTAIN",
                "evidence_sources": ["ai"],
                "matched_detections": [],
                "note": "AI reports this component visible but with low overall confidence; needs review.",
            }

    return {
        "name": component.name,
        "observation": "NOT_OBSERVED",
        "evidence_sources": [],
        "matched_detections": [],
        "note": "No supporting evidence in this photo. Not visible is not the same as missing.",
    }


def _identity_verdict(ret: ReturnRecord, ocr: OCRData, yolo: DetectionData, ai) -> dict:
    expected_sku = ret.expected_sku or ""
    norm_sku = _norm(expected_sku)
    sku_found = bool(norm_sku) and norm_sku in _norm(ocr.full_text or "")
    ocr_usable = ocr.status in ("OK", "LOW_CONFIDENCE")
    text = ocr.full_text or ""

    # Strong failure: a high-confidence conflicting printed SKU (CONF-01 basis).
    conflicting = []
    if ocr_usable and norm_sku and not sku_found and (ocr.mean_confidence or 0) >= 80:
        conflicting = [
            m.group(1)
            for m in re.finditer(
                r"\b(?:sku|model|mpn|p/n|part\s*no|part\s*number)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-/]{2,})\b",
                text, re.IGNORECASE,
            )
            if _norm(m.group(1)) != norm_sku and len(_norm(m.group(1))) >= 4
        ]

    ai_identity = ai.identity if (ai is not None and ai.status == "OK") else None
    ai_strong_fail = ai_identity == "FAIL" and (ai.confidence or 0) >= AI_IDENTITY_FAIL_FLOOR

    sources: list[str] = []
    notes: list[str] = []

    if conflicting or ai_strong_fail:
        verdict = "FAIL"
        if conflicting:
            sources.append("ocr")
            notes.append(f"High-confidence label shows a conflicting identifier ({', '.join(sorted(set(conflicting))[:3])}).")
        if ai_strong_fail:
            sources.append("ai")
            notes.append(f"{ai.provider}/{ai.model}: {ai.identity_reasoning}")
    elif sku_found and ai_identity == "PASS":
        verdict = "PASS"
        sources = ["ocr", "ai"]
        notes.append(f"Expected SKU '{expected_sku}' found in readable text and the visual assessment agrees.")
    else:
        verdict = "UNCERTAIN"
        if sku_found:
            sources.append("ocr")
            notes.append("SKU text matches, but OCR alone cannot establish physical product identity.")
        if ai_identity == "PASS":
            sources.append("ai")
            notes.append("Visual assessment supports the identity, but no readable SKU corroborates it.")
        if ai_identity == "FAIL" and not ai_strong_fail:
            sources.append("ai")
            notes.append(f"Visual assessment leans FAIL (confidence {ai.confidence}) but below the strong-evidence floor.")
        if not sources:
            notes.append("No conclusive identity evidence in this photo.")

    return {
        "verdict": verdict,
        "expected_sku": expected_sku,
        "sku_found_in_ocr": sku_found,
        "sources": sources,
        "detected_classes": sorted({d.class_label for d in yolo.detections}),
        "notes": notes,
    }


def build_evidence(ret: ReturnRecord, ocr: OCRData, yolo: DetectionData, ai=None,
                   view_type: str = "STANDARD") -> dict:
    """Build the per-photo structured evidence payload (schema v2.0)."""
    identity = _identity_verdict(ret, ocr, yolo, ai)
    components = [_component_observation(c, yolo, ai) for c in ret.expected_components]

    if ai is not None and ai.status == "OK":
        condition = {
            "grade": ai.condition_grade,
            "source": "ai",
            "assessed_by": f"{ai.provider}/{ai.model}",
            "reasoning": ai.condition_reasoning,
            "visible_defects": ai.visible_defects,
            "note": (
                "Grade comes from validated visual assessment against the configured "
                "condition scale; photographs cannot prove full functionality."
            ),
        }
    else:
        condition = {
            "grade": "UNKNOWN",
            "source": "none",
            "assessed_by": None,
            "reasoning": "",
            "visible_defects": [],
            "note": (
                "No condition grade available (AI stage "
                f"{ai.status if ai is not None else 'not run'}). No defect claims are made."
            ),
        }

    uncertainties: list[str] = []
    if identity["verdict"] != "PASS":
        uncertainties.append("Product identity is not confirmed.")
    for c in components:
        if c["observation"] != "OBSERVED":
            uncertainties.append(f"Component '{c['name']}' was not confirmed in this photo.")
    if condition["grade"] == "UNKNOWN":
        uncertainties.append("Condition grade could not be assessed.")
    if ocr.status in ("ENGINE_UNAVAILABLE", "FAILED", "TIMEOUT"):
        uncertainties.append(f"OCR evidence unavailable (status={ocr.status}).")
    if yolo.status in ("MODEL_UNAVAILABLE", "FAILED", "TIMEOUT"):
        uncertainties.append(f"Object-detection evidence unavailable (status={yolo.status}).")
    if ai is not None and ai.status != "OK":
        uncertainties.append(f"AI visual analysis unavailable (status={ai.status}).")
    if ocr.status == "LOW_CONFIDENCE":
        uncertainties.append("OCR text was extracted with low average confidence.")
    if view_type == "CONTENTS_LAYOUT":
        uncertainties.append("Contents-layout photo: absence here is meaningful for completeness.")

    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "view_type": view_type,
        "identity": identity,
        "components": components,
        "condition": condition,
        "ocr_summary": {
            "engine": ocr.engine,
            "status": ocr.status,
            "mean_confidence": ocr.mean_confidence,
            "text_excerpt": (ocr.full_text or "")[:2000],
            "processing_ms": ocr.processing_ms,
        },
        "yolo_summary": {
            "model_name": yolo.model_name,
            "status": yolo.status,
            "device": yolo.device,
            "confidence_threshold": yolo.confidence_threshold,
            "inference_ms": yolo.inference_ms,
            "detection_count": len(yolo.detections),
            "class_labels": sorted({d.class_label for d in yolo.detections}),
            "notes": yolo.notes,
        },
        "ai_summary": (
            {
                "provider": ai.provider,
                "model": ai.model,
                "status": ai.status,
                "identity": ai.identity,
                "condition_grade": ai.condition_grade,
                "confidence": ai.confidence,
                "latency_ms": ai.latency_ms,
                "attempts": ai.attempts,
                "error": ai.error,
            }
            if ai is not None
            else {"provider": "groq", "model": "", "status": "UNAVAILABLE", "error": "not run"}
        ),
        "uncertainties": uncertainties,
    }
