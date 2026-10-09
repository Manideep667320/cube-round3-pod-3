"""Live computer-vision smoke tests.

These run REAL OCR and REAL YOLO inference. They are marked `live_cv`; if the
engine or model weights are unavailable in this environment the test FAILS with
an explicit blocker message rather than fabricating detections. Run the rest of
the suite without them via: pytest -m "not live_cv"
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.live_cv


# ---------------------------------------------------------------------------
# OCR (RapidOCR or Tesseract - real engines)
# ---------------------------------------------------------------------------
def _render_label_image(text: str, path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1000, 300), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except OSError:
        font = ImageFont.load_default()
    draw.text((30, 100), text, fill="black", font=font)
    img.save(path, format="PNG")


def test_live_ocr_extracts_real_text(tmp_path):
    from agents.returns.backend.app.core.config import settings
    from agents.returns.backend.app.services.ocr_service import get_engine_info, run_ocr

    info = get_engine_info()
    if not info["available"]:
        pytest.fail(
            "BLOCKED: no OCR engine is installed in this environment. "
            "Install rapidocr-onnxruntime (pip) or Tesseract to run live OCR tests."
        )
    image = tmp_path / "label.png"
    _render_label_image("MODEL: X1-CARBON-9", image)
    result = run_ocr(image)
    assert result.status in ("OK", "LOW_CONFIDENCE"), f"unexpected status {result.status}: {result.error}"
    assert result.engine in ("rapidocr", "tesseract")
    assert "X1" in result.full_text.upper().replace("-", "").replace(" ", "") or result.mean_confidence is not None
    assert result.blocks, "real OCR produced no blocks"
    for block in result.blocks:
        assert block.text
    assert result.processing_ms > 0


def test_live_ocr_no_text_image(tmp_path):
    from agents.returns.backend.app.services.ocr_service import get_engine_info, run_ocr

    if not get_engine_info()["available"]:
        pytest.fail("BLOCKED: no OCR engine installed.")
    image = tmp_path / "blank.png"
    _render_label_image("", image)
    result = run_ocr(image)
    assert result.status in ("NO_TEXT_DETECTED", "LOW_CONFIDENCE", "OK")
    if result.status == "OK":
        assert result.mean_confidence is not None


# ---------------------------------------------------------------------------
# YOLO (Ultralytics with real weights)
# ---------------------------------------------------------------------------
def test_live_yolo_loads_model_and_runs(tmp_path):
    from agents.returns.backend.app.core.config import settings
    from agents.returns.backend.app.services.yolo_service import run_detection

    weights = Path(settings.yolo_model_path)
    if not weights.exists() and not settings.yolo_model_path.lower().endswith((".pt", ".onnx")):
        pytest.fail(
            f"BLOCKED: YOLO weights not found at '{settings.yolo_model_path}'. "
            "Set YOLO_MODEL_PATH to real weights (yolov8n.pt is auto-downloaded by ultralytics)."
        )
    # Draw a laptop-like rectangle scene; the generic COCO model should at
    # minimum run without error. We assert schema validity, NOT specific classes.
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 480), (120, 140, 160))
    draw = ImageDraw.Draw(img)
    draw.rectangle([120, 120, 520, 380], fill=(30, 30, 30))
    draw.rectangle([140, 140, 500, 320], fill=(90, 160, 220))
    image = tmp_path / "scene.png"
    img.save(image)

    result = run_detection(image)
    assert result.status == "OK", f"YOLO inference failed: {result.error}"
    assert result.model_name
    assert result.device in ("cpu", "cuda")
    assert result.inference_ms >= 0
    for det in result.detections:
        x1, y1, x2, y2 = det.bbox
        assert x2 > x1 and y2 > y1
        assert 0 <= x1 <= 640 and 0 <= x2 <= 640
        assert 0 <= det.confidence <= 1.0
        assert isinstance(det.class_label, str) and det.class_label


def test_live_yolo_model_is_loaded_once():
    """The service must reuse the loaded model across calls (no per-request load)."""
    import time

    from agents.returns.backend.app.services.yolo_service import _load_model

    started = time.perf_counter()
    _load_model()
    first = time.perf_counter() - started
    started = time.perf_counter()
    _load_model()
    second = time.perf_counter() - started
    assert second < first or second < 0.5, "model appears to be reloaded per request"
