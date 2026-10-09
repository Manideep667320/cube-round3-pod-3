"""Returns Manager Agent: Entry point.

Exposes `handle(request: dict) -> dict` and the FastAPI web service `app`.
Integrated with OCR, YOLO, Groq Qwen Vision AI, Amazon Published Condition Scale,
and contract-compliant Evidence Record generation.
"""
from __future__ import annotations

from shared.utils.server import make_app
from .engine import AGENT_ID, process_returns_request

STAGE = "returns"


def handle(request: dict) -> dict:
    """Process an Agent Input and return a contract-compliant Agent Output."""
    return process_returns_request(request)


app = make_app(STAGE, handle)
