"""W4 decision: the pure, testable core. No I/O, no randomness, no model calls.

`decide()` turns *facts* (perception + damage + operator inputs) plus the expected
manifest line into {verdict, reasons, retakeable} using plan section 4's rules:

  verdict = most severe among raised reasons   (REJECT > ESCALATE > QUARANTINE > ACCEPT)
  all raised reasons are listed
  image-quality flags never change the verdict alone; they are the *cause* of
  NO_BARCODE / LOW_CONF_DAMAGE only (test 11).

The 4-state verdict vocabulary (ACCEPT/QUARANTINE/REJECT/ESCALATE) is the plan's
physical-action vocabulary. It is mapped to the contract's PASS/FAIL/UNCERTAIN +
decision.outcome in service.py — this module stays independent of the contract.
"""
from __future__ import annotations

from datetime import date, datetime

ACCEPT = "ACCEPT"
QUARANTINE = "QUARANTINE"
REJECT = "REJECT"
ESCALATE = "ESCALATE"

RANK = {ACCEPT: 0, QUARANTINE: 1, ESCALATE: 2, REJECT: 3}

SEVERE_DAMAGE = "SEVERE_DAMAGE"
EXPIRED = "EXPIRED"
WRONG_SKU = "WRONG_SKU"
NOT_IN_MANIFEST = "NOT_IN_MANIFEST"
QTY_MISMATCH = "QTY_MISMATCH"
LOT_CONFLICT = "LOT_CONFLICT"
MODERATE_DAMAGE = "MODERATE_DAMAGE"
NO_BARCODE = "NO_BARCODE"
LOW_CONF_DAMAGE = "LOW_CONF_DAMAGE"
IMG_BLURRY = "IMG_BLURRY"
IMG_GLARE = "IMG_GLARE"
IMG_DARK = "IMG_DARK"

REASON_CODES = (SEVERE_DAMAGE, EXPIRED, WRONG_SKU, NOT_IN_MANIFEST, QTY_MISMATCH,
                LOT_CONFLICT, MODERATE_DAMAGE, LOW_CONF_DAMAGE, NO_BARCODE,
                IMG_BLURRY, IMG_GLARE, IMG_DARK)

# What each reason means for the physical action.
VERDICT_OF = {
    SEVERE_DAMAGE: REJECT, EXPIRED: REJECT,
    WRONG_SKU: ESCALATE, NOT_IN_MANIFEST: ESCALATE, QTY_MISMATCH: ESCALATE, LOT_CONFLICT: ESCALATE,
    MODERATE_DAMAGE: QUARANTINE, NO_BARCODE: QUARANTINE, LOW_CONF_DAMAGE: QUARANTINE,
}

# Only these two are worth re-shooting for; moderate damage is a fact about the goods.
RETAKEABLE = {NO_BARCODE, LOW_CONF_DAMAGE}
IMAGE_FLAGS = (IMG_BLURRY, IMG_GLARE, IMG_DARK)

# Listing order: most severe first, image diagnostics last.
REASON_ORDER = (SEVERE_DAMAGE, EXPIRED, WRONG_SKU, NOT_IN_MANIFEST, QTY_MISMATCH,
                LOT_CONFLICT, MODERATE_DAMAGE, LOW_CONF_DAMAGE, NO_BARCODE,
                IMG_BLURRY, IMG_GLARE, IMG_DARK)


def _parse_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            candidate = text[:19] if ("T" in text or " " in text) else text
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return None


def _flags_for(quality: list[dict], role: str | None = None) -> list[str]:
    out: list[str] = []
    for q in quality or []:
        if role and q.get("role") != role:
            continue
        for flag in q.get("flags", []):
            if flag not in out:
                out.append(flag)
    return out


def decide(*, facts: dict, line: dict | None, qty_received: int | None,
           lot: str, expiry: str, thresholds: dict, today: date,
           manifest_gtins: set[str] | None = None) -> dict:
    """-> {verdict, reasons[], retakeable}. Pure: all context is passed in."""
    th = thresholds
    gtins = manifest_gtins or set()
    raised: set[str] = set()

    # --- damage (model facts, with fail-safe) ---
    damage = facts.get("damage") or {}
    source = damage.get("source", "unavailable")
    severity = int(damage.get("severity") or 0)
    confidence = float(damage.get("conf") or 0.0)
    if source not in ("vlm",) or confidence < th["confidence_min"]:
        raised.add(LOW_CONF_DAMAGE)
    elif severity >= th["severe_damage_min"]:
        raised.add(SEVERE_DAMAGE)
    elif severity >= 2:
        raised.add(MODERATE_DAMAGE)

    # --- identity / barcode ---
    barcode = facts.get("barcode") or {}
    quality = facts.get("quality") or []
    label_flags = _flags_for(quality, role="label") or _flags_for(quality)
    all_flags = _flags_for(quality)

    if barcode.get("found") and (line or {}).get("gtin"):
        value = str(barcode.get("value") or "")
        expected = str(line.get("gtin") or "")
        if value and expected and value != expected:
            raised.add(WRONG_SKU if value in gtins else NOT_IN_MANIFEST)
    elif not barcode.get("found"):
        raised.add(NO_BARCODE)

    # --- reconciliation (operator-entered; skipped when not provided) ---
    expected_qty = (line or {}).get("qty_expected")
    if qty_received is not None and expected_qty is not None and int(qty_received) != int(expected_qty):
        raised.add(QTY_MISMATCH)

    lot_expected = ((line or {}).get("lot") or "").strip()
    lot_observed = (lot or "").strip()
    if lot_expected and lot_observed and lot_expected != lot_observed:
        raised.add(LOT_CONFLICT)

    expiry_due = _parse_date((line or {}).get("expiry") or "")
    expiry_seen = _parse_date(expiry or "")
    effective_expiry = expiry_seen or expiry_due
    if effective_expiry and effective_expiry < today:
        raised.add(EXPIRED)

    # --- image diagnostics: only as the cause of NO_BARCODE / LOW_CONF_DAMAGE ---
    cause_flags: list[str] = []
    if NO_BARCODE in raised:
        cause_flags = [f for f in (label_flags or all_flags) if f in IMAGE_FLAGS]
    elif LOW_CONF_DAMAGE in raised:
        cause_flags = [f for f in all_flags if f in IMAGE_FLAGS]
    raised.update(cause_flags)

    reasons = [code for code in REASON_ORDER if code in raised]
    verdict = ACCEPT
    for code in reasons:
        candidate = VERDICT_OF.get(code)
        if candidate and RANK[candidate] > RANK[verdict]:
            verdict = candidate

    return {"verdict": verdict, "reasons": reasons,
            "retakeable": any(code in RETAKEABLE for code in reasons)}


def contract_view(verdict: str) -> tuple[str, str, str]:
    """4-state plan verdict -> (contract verdict, decision.outcome, next_step)."""
    return {
        ACCEPT: ("PASS", "accept", "continue"),
        QUARANTINE: ("UNCERTAIN", "pending_review", "review"),
        ESCALATE: ("FAIL", "pending_review", "review"),
        REJECT: ("FAIL", "reject", "route_to_recovery"),
    }[verdict]
