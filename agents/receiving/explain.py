"""W4 explanation: one string template per reason code, interpolating real values.

No LLM text: the card must show numbers that are actually in `facts` (contract
rule: never fabricate). Test 15 asserts no template placeholder survives.
"""
from __future__ import annotations

from .decide import (EXPIRED, IMG_BLURRY, IMG_DARK, IMG_GLARE, LOW_CONF_DAMAGE,
                     LOT_CONFLICT, MODERATE_DAMAGE, NO_BARCODE, NOT_IN_MANIFEST,
                     QTY_MISMATCH, REASON_ORDER, SEVERE_DAMAGE, WRONG_SKU)

TEMPLATES = {
    SEVERE_DAMAGE: "Severe {damage_type} damage, severity {severity}/5 at confidence {confidence:.2f} - the goods cannot be received.",
    EXPIRED: "Expiry {expiry} is in the past (today is {today}).",
    WRONG_SKU: "Barcode {barcode} is real stock, but not for this line (expected GTIN {expected_gtin}).",
    NOT_IN_MANIFEST: "Barcode {barcode} is not on any line of this manifest.",
    QTY_MISMATCH: "Quantity received {qty_received} vs {qty_expected} expected (delta {delta:+d} units).",
    LOT_CONFLICT: "Lot observed {lot_observed} differs from the manifest lot {lot_expected}.",
    MODERATE_DAMAGE: "Moderate {damage_type} damage, severity {severity}/5 at confidence {confidence:.2f}.",
    NO_BARCODE: "No barcode could be decoded from {photo_count} photo(s).",
    LOW_CONF_DAMAGE: "Damage assessment not conclusive: source {damage_source}, confidence {confidence:.2f} below threshold {confidence_min:.2f}.",
    IMG_BLURRY: "Blur variance {blur_value} is below the minimum {blur_min_variance} - the image is blurry.",
    IMG_GLARE: "Glare covers {glare_value:.1%} of pixels (limit {glare_max_ratio:.1%}).",
    IMG_DARK: "Luminance {luminance_value} is outside the accepted {lum_min}-{lum_max} range.",
}


def _worst_photo(facts: dict, flag: str) -> dict:
    for q in facts.get("quality") or []:
        if flag in (q.get("flags") or []):
            return q
    return {}


def _values(*, facts: dict, line: dict | None, qty_received, lot, expiry,
            thresholds: dict, today, photo_count: int) -> dict:
    line = line or {}
    damage = facts.get("damage") or {}
    barcode = facts.get("barcode") or {}
    th = thresholds
    expected = line.get("qty_expected")
    delta = (qty_received - expected) if (qty_received is not None and expected is not None) else 0
    blurry = _worst_photo(facts, IMG_BLURRY)
    glare = _worst_photo(facts, IMG_GLARE)
    dark = _worst_photo(facts, IMG_DARK)
    return {
        "damage_type": damage.get("type") or "unknown",
        "severity": int(damage.get("severity") or 0),
        "confidence": float(damage.get("conf") or 0.0),
        "damage_source": damage.get("source") or "unavailable",
        "confidence_min": th["confidence_min"],
        "expiry": expiry or line.get("expiry") or "unknown",
        "today": today.isoformat(),
        "barcode": barcode.get("value") or "unknown",
        "expected_gtin": line.get("gtin") or "unknown",
        "qty_received": qty_received if qty_received is not None else "not given",
        "qty_expected": expected if expected is not None else "not given",
        "delta": delta,
        "lot_observed": (lot or "").strip() or "(none)",
        "lot_expected": (line.get("lot") or "").strip() or "(none)",
        "photo_count": photo_count,
        "blur_value": blurry.get("blur", "n/a"),
        "blur_min_variance": th["blur_min_variance"],
        "glare_value": float(glare.get("glare") or 0.0),
        "glare_max_ratio": th["glare_max_ratio"],
        "luminance_value": dark.get("luminance", "n/a"),
        "lum_min": th["lum_min"],
        "lum_max": th["lum_max"],
    }


def explain(reasons, *, facts, line, qty_received, lot, expiry, thresholds, today,
            photo_count: int) -> list[dict]:
    """-> [{"code": ..., "text": ...}] in the canonical reason order."""
    values = _values(facts=facts, line=line, qty_received=qty_received, lot=lot,
                     expiry=expiry, thresholds=thresholds, today=today,
                     photo_count=photo_count)
    out = []
    for code in REASON_ORDER:
        if code in reasons:
            out.append({"code": code, "text": TEMPLATES[code].format(**values)})
    return out
