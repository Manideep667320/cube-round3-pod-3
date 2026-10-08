from __future__ import annotations

from collections.abc import Iterable

from agents.recovery.adapters import chain_evidence, make_check, parse_csv_rows


def _verdict(value: str | None, positives: set[str], negatives: set[str]) -> str:
    normalized = (value or "").strip().lower()
    if normalized in positives:
        return "pass"
    if normalized in negatives:
        return "fail"
    return "uncertain"


def adapt_prep(raw: bytes | str, previous_evidence: Iterable[dict[str, object]] = ()) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row in parse_csv_rows(raw):
        bagging = row.get("polybag_present_sealed")
        warning = row.get("suffocation_warning")
        placement = row.get("fnsku_label_placement")
        checks = [
            make_check("prep", "polybag_present", _verdict(bagging, {"sealed", "not_sealed", "yes"}, {"missing", "no", "not_present"}), row),
            make_check("prep", "polybag_sealed", _verdict(bagging, {"sealed", "yes"}, {"not_sealed", "unsealed"}), row),
            make_check("prep", "suffocation_warning_present", _verdict(warning, {"legible", "illegible", "present"}, {"missing", "absent"}), row),
            make_check("prep", "suffocation_warning_legible", _verdict(warning, {"legible"}, {"illegible", "illegible_or_missing"}), row),
            make_check("prep", "fnsku_label_flat", _verdict(placement, {"flat"}, {"on_seam", "folded", "wrinkled"}), row),
            make_check("prep", "manufacturer_barcode_covered", _verdict(row.get("original_barcode_covered"), {"yes", "true"}, {"no", "false"}), row),
            make_check("prep", "expiry_date_legible", _verdict(row.get("expiry_date"), {"legible"}, {"illegible"}), row),
            make_check("prep", "handling_marks_present", _verdict(row.get("handling_marks"), {"all_present", "present", "yes"}, {"missing", "none", "no"}), row),
        ]
        records.append(
            {
                "manager": "prep",
                "source_record_id": row.get("record_id"),
                "org_id": row.get("org_id"),
                "unit_id": row.get("unit_id"),
                "observed_at": row.get("captured_at"),
                "photo_refs": row.get("photo_refs", "").split(";") if row.get("photo_refs") else [],
                "observations": {
                    "polybag_present_sealed": row.get("polybag_present_sealed"),
                    "suffocation_warning": row.get("suffocation_warning"),
                    "fnsku_label_placement": row.get("fnsku_label_placement"),
                    "original_barcode_covered": row.get("original_barcode_covered"),
                    "expiry_date": row.get("expiry_date"),
                    "handling_marks": row.get("handling_marks"),
                },
                "checks": checks,
                "verdict": "uncertain",
            }
        )
    return chain_evidence(records, previous_evidence)