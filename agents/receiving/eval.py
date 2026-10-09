"""Evaluation harness for Receiving Manager over sample dataset (100 units).

Evaluates decision engine accuracy, identity matching, quantity verification,
and damage classification across the 100 sample units in data/sample/receiving_sample.csv.

Run:   python -m agents.receiving.eval
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

from . import config, db, decide as D

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CSV = ROOT / "data" / "sample" / "receiving_sample.csv"

DAMAGE_SEVERITY = {
    "none": 0,
    "scuff": 1,
    "minor": 1,
    "tears": 2,
    "crushing": 4,
    "water": 4,
    "uncertain": 0,
}


def load_sample_units(split: str | None = None) -> list[dict]:
    with open(SAMPLE_CSV, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    # 70 train (UNIT-0001 to UNIT-0070), 30 hold-out (UNIT-0071 to UNIT-0100)
    if split == "train":
        return rows[:70]
    if split == "holdout":
        return rows[70:]
    return rows


def evaluate_row(r: dict, th: dict) -> dict:
    today = date.today()
    co, cr = int(r["cartons_ordered"]), int(r["cartons_received"])
    qo, qr = int(r["qty_ordered"]), int(r["qty_received"])
    cdamage = r.get("carton_damage", "none").lower()
    udamage = r.get("unit_damage", "none").lower()
    id_match = r.get("identity_match", "yes").lower() == "yes"

    sev = max(DAMAGE_SEVERITY.get(cdamage, 0), DAMAGE_SEVERITY.get(udamage, 0))
    conf = 0.50 if "uncertain" in (cdamage, udamage) else (0.95 if sev > 0 else 0.98)

    facts = {
        "barcode": {
            "found": id_match,
            "value": r["sku"] if id_match else "WRONG-SKU",
            "format": "Code128",
            "photo_role": "label"
        },
        "quality": [{"role": "label", "blur": 150.0, "glare": 0.02, "luminance": 128, "flags": []}],
        "damage": {
            "source": "vlm",
            "severity": sev,
            "conf": conf,
            "reason": f"carton: {cdamage}, unit: {udamage}"
        },
        "photo_count": 3
    }

    line = {
        "id": int(r.get("po_line") or 1),
        "po_id": r["po_number"],
        "line_no": int(r["po_line"]),
        "gtin": r["sku"],
        "sku": r["sku"],
        "asin": r["asin"],
        "qty_expected": qo,
        "lot": "",
        "expiry": "",
        "supplier": r["supplier"]
    }

    decision = D.decide(
        facts=facts,
        line=line,
        qty_received=qr,
        lot="",
        expiry="",
        thresholds=th,
        today=today,
        manifest_gtins={r["sku"]}
    )

    expected_action = D.ACCEPT
    if not id_match:
        expected_action = D.ESCALATE
    elif qo != qr:
        expected_action = D.ESCALATE
    elif sev >= th["severe_damage_min"]:
        expected_action = D.REJECT
    elif sev >= 2 or "uncertain" in (cdamage, udamage):
        expected_action = D.QUARANTINE

    return {
        "row": r,
        "facts": facts,
        "decision": decision,
        "expected_action": expected_action,
        "correct": decision["verdict"] == expected_action
    }


def report(split: str, results: list[dict]) -> dict:
    n = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = round(correct / n, 3) if n else 0.0

    qty_expected = sum(1 for r in results if int(r["row"]["qty_ordered"]) != int(r["row"]["qty_received"]))
    qty_detected = sum(1 for r in results if D.QTY_MISMATCH in r["decision"]["reasons"])

    id_fail_expected = sum(1 for r in results if r["row"]["identity_match"].lower() != "yes")
    id_fail_detected = sum(1 for r in results if D.WRONG_SKU in r["decision"]["reasons"] or D.NO_BARCODE in r["decision"]["reasons"])

    verdicts = {v: sum(1 for r in results if r["decision"]["verdict"] == v)
                for v in (D.ACCEPT, D.QUARANTINE, D.ESCALATE, D.REJECT)}

    return {
        "split": split,
        "total_units": n,
        "accuracy": accuracy,
        "correct_count": correct,
        "quantity_mismatches": {"expected": qty_expected, "detected": qty_detected},
        "identity_discrepancies": {"expected": id_fail_expected, "detected": id_fail_detected},
        "verdicts": verdicts
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    db.init_db()
    th = config.thresholds()

    train = [evaluate_row(r, th) for r in load_sample_units("train")]
    holdout = [evaluate_row(r, th) for r in load_sample_units("holdout")]

    print("============================================================")
    print("RECEIVING MANAGER BENCHMARK EVALUATION (Sample Dataset n=100)")
    print("============================================================")
    for split_name, results in (("Train (UNIT-0001 to UNIT-0070)", train),
                               ("Hold-out (UNIT-0071 to UNIT-0100)", holdout)):
        res = report(split_name, results)
        print(f"\n--- {res['split']} (n={res['total_units']}) ---")
        print(f"  Overall Accuracy:        {res['accuracy'] * 100:.1f}% ({res['correct_count']}/{res['total_units']})")
        print(f"  Quantity Mismatches:     {res['quantity_mismatches']['detected']}/{res['quantity_mismatches']['expected']} detected")
        print(f"  Identity Discrepancies:  {res['identity_discrepancies']['detected']}/{res['identity_discrepancies']['expected']} detected")
        print(f"  Decision Breakdown:      {res['verdicts']}")
    print("============================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
