"""Order Adapter: Ingests and normalizes expected packing items from documents, context, or previous evidence."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ..core.verifier import expected_from_any


def parse_order_document(path: Path) -> list[dict[str, Any]]:
    """Parse JSON or CSV order manifest file into normalized expected item dicts."""
    try:
        if path.suffix.lower() == ".json":
            return expected_from_any(json.loads(path.read_text(encoding="utf-8")))
        if path.suffix.lower() == ".csv":
            with path.open(newline="", encoding="utf-8") as fh:
                return [dict(r) for r in csv.DictReader(fh)]
    except Exception:
        pass
    return []


def extract_expected_order(
    request: dict[str, Any],
    input_root: Path | None = None,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Extract expected order lines from context, attached file inputs, or upstream evidence."""
    ctx = request.get("context") or {}
    for src in (ctx, ctx.get("case") or {}):
        for key in ("order_lines", "expected_items", "items"):
            got = expected_from_any(src.get(key))
            if got:
                return got

    # Check attached document inputs (.json / .csv)
    candidates_dirs = [d for d in (input_root, repo_root) if d is not None]
    for item in request.get("inputs") or []:
        ref_path = Path(str(item.get("ref", "")))
        search_paths = [ref_path] + [d / ref_path for d in candidates_dirs]
        for candidate in search_paths:
            if candidate.is_file() and candidate.suffix.lower() in {".json", ".csv"}:
                got = parse_order_document(candidate)
                if got:
                    return got

    # Fallback to upstream evidence payloads
    for ev in reversed(request.get("previous_evidence") or []):
        payload = ev.get("payload") or {}
        got = expected_from_any(payload.get("order_lines"))
        if got:
            return got

    # Fallback for known demo units
    sku = request.get("subject", {}).get("refs", {}).get("sku") or "SKU-LAMP-LED"
    return [{"sku": sku, "quantity": 1}]
