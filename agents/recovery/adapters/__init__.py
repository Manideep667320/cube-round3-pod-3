from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from agents.recovery.domain.validation import RecoveryInputError


def parse_csv_rows(raw: bytes | str) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if not reader.fieldnames or any(not name for name in reader.fieldnames):
            raise RecoveryInputError("CSV requires non-empty headers")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise RecoveryInputError("CSV has duplicate headers")
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise RecoveryInputError("CSV is malformed or not UTF-8") from exc
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise RecoveryInputError("CSV row width does not match headers")
    return [{str(key): str(value) for key, value in row.items()} for row in rows]


def chain_evidence(
    records: Iterable[dict[str, object]], previous_evidence: Iterable[dict[str, object]] = ()
) -> list[dict[str, object]]:
    previous = list(previous_evidence)
    charges = [
        item for item in previous
        if item.get("manager") == "fee_report" and isinstance(item.get("charge_id"), str)
    ]
    linked: list[dict[str, object]] = []
    for record in records:
        matches = [
            item for item in charges
            if item.get("org_id") == record.get("org_id") and item.get("unit_id") == record.get("unit_id")
        ]
        linked_record = dict(record)
        linked_record["attributed_charge_ids"] = [item["charge_id"] for item in matches]
        if len(matches) == 1:
            linked_record["attributed_charge_id"] = matches[0]["charge_id"]
            for check in linked_record.get("checks", []):
                check["attributed_charge_id"] = matches[0]["charge_id"]
        linked.append(linked_record)
    return [*previous, *linked]


def make_check(
    manager: str,
    check_key: str,
    verdict: str,
    row: dict[str, str],
) -> dict[str, object]:
    observed_at = row.get("captured_at", "")
    return {
        "manager": manager,
        "check_key": check_key,
        "verdict": verdict if verdict in {"pass", "fail", "uncertain"} else "uncertain",
        "observed_at": observed_at[:10],
        "granularity": "unit",
        "shipment_id": row.get("fba_shipment_id") or None,
        "amazon_order_id": row.get("order_id") or None,
        "attributed_charge_id": None,
    }


def flatten_checks(records: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return [check for record in records for check in record.get("checks", [])]