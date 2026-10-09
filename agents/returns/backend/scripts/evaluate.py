"""Evaluation report generator.

Runs the 15 labeled challenge-alignment scenarios (tests/test_evaluation_scenarios.py)
against the REAL evidence builder + decision engine and prints per-scenario
results plus per-task metrics.

Scope statement (read before citing these numbers):
- This measures DECISION-LOGIC agreement with ground-truth labels under
  deterministic (mocked) OCR/YOLO/AI inputs - i.e. the correctness of evidence
  aggregation, dimension verdicts and disposition rules.
- It does NOT measure model accuracy on real photographs; no labeled real-photo
  dataset is available in this environment. Model-level verification lives in
  the live tests: `pytest -m live_cv` (real RapidOCR + real YOLO) and
  `RUN_LIVE_GROQ=1 pytest -m groq_live` (real Groq/Qwen inference).

Usage: python -m scripts.evaluate
"""
from __future__ import annotations

import sys
import traceback

from agents.returns.backend.tests import test_evaluation_scenarios as scen

TASKS = {
    "scenario_01": "identity", "scenario_02": "identity", "scenario_03": "identity",
    "scenario_04": "completeness", "scenario_05": "completeness", "scenario_06": "completeness",
    "scenario_07": "condition", "scenario_08": "condition", "scenario_09": "condition",
    "scenario_10": "condition", "scenario_11": "condition", "scenario_12": "identity",
    "scenario_13": "identity", "scenario_14": "completeness", "scenario_15": "resilience",
}


def main() -> int:
    tests = sorted(
        (name, fn) for name, fn in vars(scen).items()
        if name.startswith("test_scenario_") and callable(fn)
    )
    results: list[tuple[str, str, bool, str]] = []
    for name, fn in tests:
        label = name.replace("test_", "")
        try:
            fn()
            results.append((label, TASKS.get(label.split("_")[0] + "_" + label.split("_")[1], "?"), True, ""))
        except Exception:  # noqa: BLE001
            results.append((label, TASKS.get(label.split("_")[0] + "_" + label.split("_")[1], "?"), False,
                            traceback.format_exc(limit=1).strip().splitlines()[-1]))

    width = max(len(r[0]) for r in results) + 2
    print("=" * 78)
    print("ReturnGuard AI - challenge-alignment evaluation (decision logic, mocked engines)")
    print(f"sample size: {len(results)} labeled scenarios | conditions: deterministic OCR/YOLO/AI inputs")
    print("=" * 78)
    for label, task, ok, err in results:
        print(f"  {label:<{width}} task={task:<13} {'PASS' if ok else 'FAIL'}  {err}")

    total = len(results)
    passed = sum(1 for r in results if r[2])
    print("-" * 78)
    for task in sorted({r[1] for r in results}):
        subset = [r for r in results if r[1] == task]
        ok = sum(1 for r in subset if r[2])
        print(f"  {task:<15} {ok}/{len(subset)} scenarios match ground truth")
    print(f"  {'TOTAL':<15} {passed}/{total}")
    print("-" * 78)
    print("Model-accuracy caveat: these results validate decision logic, not CV/LLM")
    print("accuracy on real photos (no labeled dataset available here).")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
