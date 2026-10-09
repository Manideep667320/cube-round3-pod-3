"""W4 retake coach: retakeable reason -> one instruction + the photo role to re-shoot.

The coach reacts to image quality and model confidence, NOT to ground truth
(plan section 13: disclosed limitation). One prompt only: the retake cap in
service.py makes sure `attempt == 0` is the only time this is ever shown.
"""
from __future__ import annotations

from .decide import IMG_BLURRY, IMG_DARK, IMG_GLARE, LOW_CONF_DAMAGE, NO_BARCODE

# A specific image fix beats a generic "no barcode" hint: fix the cause first.
PRIORITY = (IMG_BLURRY, IMG_GLARE, IMG_DARK, NO_BARCODE, LOW_CONF_DAMAGE)

INSTRUCTIONS = {
    IMG_BLURRY: ("Image is blurry. Hold steady and let the camera focus.", "flag"),
    IMG_GLARE: ("Glare on the label. Tilt the package away from the light.", "flag"),
    IMG_DARK: ("Too dark. Move to better light.", "flag"),
    NO_BARCODE: ("No barcode found. Move closer and center the label.", "label"),
    LOW_CONF_DAMAGE: ("Damage unclear. Take a close-up of the affected area.", "closeup"),
}


def _role_of_flag(facts: dict, flag: str, default: str) -> str:
    for q in facts.get("quality") or []:
        if flag in (q.get("flags") or []) and q.get("role"):
            return q["role"]
    return default


def coach(reasons, facts: dict | None = None) -> dict | None:
    """-> {"instruction": str, "photo_role": str} for the first actionable reason, else None."""
    for code in PRIORITY:
        if code in reasons:
            instruction, role_kind = INSTRUCTIONS[code]
            if role_kind == "flag":
                role = _role_of_flag(facts or {}, code, "label")
            else:
                role = role_kind
            return {"instruction": instruction, "photo_role": role, "reason": code}
    return None
