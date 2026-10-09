"""CUBE Round 3 Pack Manager entry point."""
from shared.utils.server import make_app
from .core.agent import handle

STAGE = "pack"
app = make_app(STAGE, handle, version="3.0.0")
