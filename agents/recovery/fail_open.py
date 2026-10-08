from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def fail_open_boundary(function: Callable[P, R]) -> Callable[P, R | dict[str, str]]:
    """Turn an unexpected decision failure into a non-blocking uncertain result."""

    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R | dict[str, str]:
        try:
            return function(*args, **kwargs)
        except Exception as exc:
            return {
                "verdict": "uncertain",
                "status": "pending",
                "reason": "DECISION_UNAVAILABLE",
                "error_type": type(exc).__name__,
            }

    return wrapped