from __future__ import annotations

import json
import sys
from typing import Any

from agents.recovery.app import handle


def main() -> int:
    try:
        request: Any = json.load(sys.stdin)
    except json.JSONDecodeError:
        json.dump({"verdict": "uncertain", "status": "pending", "reason": "INVALID_JSON"}, sys.stdout)
        sys.stdout.write("\n")
        return 2
    if not isinstance(request, dict):
        json.dump({"verdict": "uncertain", "status": "pending", "reason": "INVALID_REQUEST"}, sys.stdout)
        sys.stdout.write("\n")
        return 2
    json.dump(handle(request), sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())