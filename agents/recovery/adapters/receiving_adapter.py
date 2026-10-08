from __future__ import annotations

from collections.abc import Iterable

from agents.recovery.adapters import chain_evidence, make_check, parse_csv_rows


def _observed(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return {"yes": "pass", "no": "fail", "uncertain": "uncertain"}.get(normalized, "uncertain")


def adapt_receiving(
    raw: bytes | str, previous_evidence: Iterable[dict[str, object]] = ()
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row in parse_csv_rows(raw):
        try:
            quantity_matches = "pass" if int(row["qty_received"]) == int(row["qty_ordered"]) else "fail"
        except (KeyError, ValueError):
            quantity_matches = "uncertain"
        carton = (row.get("carton_damage") or "").strip().lower()
        unit = (row.get("unit_damage") or "").strip().lower()
        checks = [
            make_check("receiving", "identity_matches_po", _observed(row.get("identity_match")), row),
            make_check("receiving", "quantity_matches_po", quantity_matches, row),
            make_check("receiving", "carton_undamaged", "pass" if carton == "none" else "fail" if carton else "uncertain", row),
            make_check("receiving", "unit_undamaged", "pass" if unit == "none" else "fail" if unit else "uncertain", row),
        ]
        records.append(
            {
                "manager": "receiving",
                "source_record_id": row.get("record_id"),
                "org_id": row.get("org_id"),
                "unit_id": row.get("unit_id"),
                "observed_at": row.get("captured_at"),
                "observations": {
                    "identity_matches_po": _observed(row.get("identity_match")),
                    "quantity_matches_po": quantity_matches,
                    "carton_damage": row.get("carton_damage"),
                    "unit_damage": row.get("unit_damage"),
                    "dimensions": None,
                    "weight": None,
                },
                "checks": checks,
                "verdict": "uncertain",
            }
        )
    return chain_evidence(records, previous_evidence)