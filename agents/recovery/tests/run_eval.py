from __future__ import annotations

import json
import sys
from typing import Any

from agents.recovery.app import handle


def main() -> int:
    """Emit predictions for supplied JSON requests; this does not calculate accuracy."""
    requests: Any = json.load(sys.stdin)
    if not isinstance(requests, list):
        raise ValueError("evaluation input must be a JSON list of requests")
    predictions = [handle(request) for request in requests]
    json.dump({"mode": "prediction_only", "predictions": predictions}, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())