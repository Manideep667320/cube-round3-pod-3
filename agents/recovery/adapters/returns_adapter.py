from __future__ import annotations

from collections.abc import Iterable

from agents.recovery.adapters import chain_evidence, make_check, parse_csv_rows
from agents.recovery.adapters.receiving_adapter import _observed


def adapt_returns(
    raw: bytes | str, previous_evidence: Iterable[dict[str, object]] = ()
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row in parse_csv_rows(raw):
        checks = [
            make_check("returns", "identity_matches_order", _observed(row.get("identity_match")), row),
            make_check("returns", "completeness_verified", "uncertain", row),
            make_check("returns", "condition_grade", "uncertain", row),
            make_check("returns", "disposition_assigned", "pass" if row.get("operator_disposition") else "uncertain", row),
        ]
        records.append(
            {
                "manager": "returns",
                "source_record_id": row.get("record_id"),
                "org_id": row.get("org_id"),
                "unit_id": row.get("unit_id"),
                "observed_at": row.get("captured_at"),
                "observations": {
                    "identity_matches_order": _observed(row.get("identity_match")),
                    "completeness_verified": "uncertain",
                    "condition_observed": row.get("observed_state"),
                    "disposition_assigned": "pass" if row.get("operator_disposition") else "uncertain",
                    "photo_refs": row.get("photo_refs", "").split(";") if row.get("photo_refs") else [],
                },
                "checks": checks,
                "verdict": "uncertain",
            }
        )
    return chain_evidence(records, previous_evidence)