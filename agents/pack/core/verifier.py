from __future__ import annotations
from collections import Counter
from typing import Any
from .models import ExpectedItem, ObservedItem

def _key(sku: str | None, name: str | None) -> str:
    return (sku or name or "").strip().casefold()

def normalize_expected(items: list[dict[str, Any]]) -> list[ExpectedItem]:
    out=[]
    for x in items:
        sku=str(x.get("sku") or x.get("item_code") or x.get("product_id") or "").strip()
        name=x.get("name") or x.get("item_name") or x.get("description")
        qty=int(x.get("quantity", x.get("qty", 1)) or 1)
        if sku or name:
            out.append(ExpectedItem(sku=sku or str(name), quantity=max(1,qty), name=str(name) if name else None))
    return out

def normalize_observed(items: list[dict[str, Any]]) -> list[ObservedItem]:
    out=[]
    for x in items:
        sku=x.get("sku") or x.get("item_code") or x.get("product_id")
        name=str(x.get("name") or x.get("item_name") or x.get("description") or "").strip()
        qty=int(x.get("quantity", x.get("qty", 1)) or 1)
        out.append(ObservedItem(sku=str(sku).strip() if sku else None,name=name,quantity=max(1,qty),confidence=float(x["confidence"]) if x.get("confidence") is not None else None,attributes=x.get("attributes") if isinstance(x.get("attributes"),dict) else None))
    return out

def verify_pack(expected: list[dict[str,Any]], observed: list[dict[str,Any]]) -> dict[str,Any]:
    exp=normalize_expected(expected); obs=normalize_observed(observed)
    exp_by=Counter(); obs_by=Counter()
    for x in exp: exp_by[_key(x.sku,x.name)] += x.quantity
    for x in obs: obs_by[_key(x.sku,x.name)] += x.quantity
    missing={k:exp_by[k]-obs_by[k] for k in exp_by if obs_by[k] < exp_by[k]}
    extra={k:obs_by[k]-exp_by[k] for k in obs_by if k not in exp_by}
    uncertain_identity=[o.name for o in obs if not o.sku and o.name and _key(None,o.name) not in exp_by]
    quantities_ok=all(obs_by[k] == exp_by[k] for k in exp_by)
    return {"expected":dict(sorted(exp_by.items())),"observed":dict(sorted(obs_by.items())),"missing":dict(sorted(missing.items())),"extra":dict(sorted(extra.items())),"wrong":[],"uncertain_identity":sorted(set(uncertain_identity)),"quantities_ok":quantities_ok,"identity_confident":not uncertain_identity,"pass":not missing and not extra and quantities_ok and not uncertain_identity}

def expected_from_any(value: Any) -> list[dict[str,Any]]:
    if isinstance(value,list): return [x for x in value if isinstance(x,dict)]
    if isinstance(value,dict):
        for key in ("order_lines","expected_items","items","lines"):
            if key in value: return expected_from_any(value[key])
    return []
