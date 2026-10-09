"""Condition scale and disposition policy.

⚠ OFFICIAL-RESOURCE GAP (see docs/GAP_ANALYSIS.md) ⚠
The Cube Build-A-Thon Returns Manager challenge references an "actual published
condition scale" in its supplied resources, but that scale is not publicly
available. This module therefore ships an explicitly UNOFFICIAL placeholder
scale so the pipeline is complete and testable. Replace it by pointing
`CONDITION_SCALE_FILE` at the official JSON (identical structure) once you have
the challenge resources — the decision engine reads grades and rules from here
and never hardcodes them.

Placeholder grades (A..E) and the deterministic disposition policy are defined
in PLACEHOLDER_POLICY below; every decision that uses them is tagged with
`policy_version` so downstream consumers can tell which rules produced it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agents.returns.backend.app.core.config import settings

POLICY_VERSION = "placeholder-v1"

PLACEHOLDER_SCALE = {
    "name": "UNOFFICIAL-PLACEHOLDER",
    "grades": [
        {"code": "A_NEW", "label": "New / unused", "definition": "No visible wear; packaging condition new-like."},
        {"code": "B_LIGHT", "label": "Light wear", "definition": "Minor cosmetic wear, fully functional appearance."},
        {"code": "C_MODERATE", "label": "Moderate wear", "definition": "Visible wear or minor damage; repairable."},
        {"code": "D_DAMAGED", "label": "Damaged", "definition": "Significant damage; parts likely missing or broken."},
        {"code": "E_NON_FUNCTIONAL", "label": "Non-functional / destroyed", "definition": "Beyond economical repair."},
        {"code": "UNKNOWN", "label": "Undetermined", "definition": "Evidence insufficient to assign a grade."},
    ],
}

# Deterministic disposition policy (UNOFFICIAL placeholder):
#   grade A_NEW        -> RESTOCK
#   grade B_LIGHT      -> RESTOCK
#   grade C_MODERATE   -> REFURBISH
#   grade D_DAMAGED    -> LIQUIDATE
#   grade E_NON_FUNC   -> DISPOSE
#   grade UNKNOWN      -> no confident recommendation (human review)
# Completeness FAIL (confirmed missing accessory) downgrades RESTOCK -> REFURBISH.
# Identity FAIL -> recommendation withheld; routed to human review.
GRADE_TO_DISPOSITION = {
    "A_NEW": "RESTOCK",
    "B_LIGHT": "RESTOCK",
    "C_MODERATE": "REFURBISH",
    "D_DAMAGED": "LIQUIDATE",
    "E_NON_FUNCTIONAL": "DISPOSE",
    "UNKNOWN": None,
}

_VALID_GRADES = tuple(g["code"] for g in PLACEHOLDER_SCALE["grades"])


@dataclass
class ConditionScale:
    name: str
    grades: list[dict]
    policy_version: str
    source: str  # "placeholder" | "file"

    @property
    def grade_codes(self) -> tuple[str, ...]:
        return tuple(g["code"] for g in self.grades)

    def disposition_for_grade(self, grade: str | None) -> str | None:
        if grade is None or grade not in self.grade_codes:
            return None
        return GRADE_TO_DISPOSITION.get(grade)


def get_condition_scale() -> ConditionScale:
    """Load the condition scale: official file when configured, else placeholder."""
    path = (settings.condition_scale_file or "").strip()
    if path:
        p = Path(path)
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                grades = data["grades"]
                # Validate structure before trusting it.
                codes = [g["code"] for g in grades]
                assert data.get("name") and codes and "UNKNOWN" in codes
                return ConditionScale(
                    name=data["name"], grades=grades,
                    policy_version=data.get("policy_version", "file-v1"), source="file",
                )
            except (ValueError, KeyError, AssertionError, OSError):
                # Fall through to placeholder rather than crashing the pipeline;
                # the health endpoint reports which scale is active.
                pass
    return ConditionScale(
        name=PLACEHOLDER_SCALE["name"], grades=PLACEHOLDER_SCALE["grades"],
        policy_version=POLICY_VERSION, source="placeholder",
    )


def valid_grade(grade: str | None) -> str | None:
    if grade in _VALID_GRADES:
        return grade
    return None
