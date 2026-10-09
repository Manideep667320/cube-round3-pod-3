"""Amazon Published Condition Scale & Disposition Mapping Rules for Returns Manager.

Standard Amazon Condition Scale:
- New: Unopened, original factory seal intact.
- Used - Like New: Opened, unused, perfect condition, original packaging intact.
- Used - Very Good: Minor cosmetic wear or opened packaging, fully functional.
- Used - Good: Moderate signs of use, fully functional, minor cosmetic blemishes.
- Used - Acceptable: Heavy signs of use, functional, cosmetic wear or missing non-essential items.
- Unsellable: Damaged, defective, non-functional, missing core components, or unsafe.
"""
from __future__ import annotations

from typing import Any

AMAZON_CONDITION_SCALE = {
    "factory_sealed": "New",
    "opened_unused": "Used - Like New",
    "signs_of_use": "Used - Very Good",
    "moderate_use": "Used - Good",
    "heavy_use": "Used - Acceptable",
    "damaged": "Unsellable",
    "defective": "Unsellable",
    "uncertain": "Uncertain",
}


def classify_amazon_condition(observed_state: str, missing_parts: list[str] | None = None, is_damaged: bool = False) -> str:
    """Map observed physical state and missing parts to Amazon's published condition grade."""
    if is_damaged:
        return "Unsellable"
    
    state_clean = (observed_state or "").lower().strip()
    
    if missing_parts and len(missing_parts) > 1:
        return "Unsellable"
    
    base_condition = AMAZON_CONDITION_SCALE.get(state_clean, "Used - Very Good")
    if missing_parts and base_condition in ("New", "Used - Like New"):
        return "Used - Good"
        
    return base_condition


def determine_disposition(condition_grade: str, missing_parts: list[str] | None = None, identity_verdict: str = "PASS") -> tuple[str, bool, str]:
    """Determine evidence-backed disposition recommendation based on condition grade and completeness.
    
    Returns:
        (disposition, needs_human, reason)
    """
    if identity_verdict == "FAIL":
        return "dispose", False, "Product identity mismatch: returned item does not match ordered SKU."
    
    if identity_verdict == "UNCERTAIN":
        return "pending_review", True, "Product identity uncertain due to unclear label/photo evidence."

    if condition_grade == "Unsellable":
        if missing_parts:
            return "dispose", False, f"Unsellable item with missing components: {', '.join(missing_parts)}."
        return "liquidate", False, "Item is damaged/unsellable; recommended for liquidation or disposal."

    if condition_grade == "New":
        return "restock", False, "Item is factory sealed / pristine New condition; safe for restock."

    if condition_grade == "Used - Like New":
        if missing_parts:
            return "refurbish", False, f"Like New item missing minor parts ({', '.join(missing_parts)}); needs refurbishment."
        return "restock", False, "Item is in Like New condition with all accessories present; suitable for restock."

    if condition_grade in ("Used - Very Good", "Used - Good"):
        if missing_parts:
            return "refurbish", False, f"Item has minor wear and missing parts ({', '.join(missing_parts)}); refurbish before relisting."
        return "refurbish", False, "Item shows signs of use; recommended for refurbishment or repackaging."

    if condition_grade == "Used - Acceptable":
        return "liquidate", False, "Item shows significant wear; recommended for liquidation."

    return "pending_review", True, "Condition or evidence uncertain; requires human operator review."
