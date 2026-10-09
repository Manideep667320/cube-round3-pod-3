from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ExpectedItem:
    sku: str
    quantity: int
    name: str | None = None

@dataclass(frozen=True)
class ObservedItem:
    sku: str | None
    name: str
    quantity: int
    confidence: float | None = None
    attributes: dict[str, Any] | None = None
