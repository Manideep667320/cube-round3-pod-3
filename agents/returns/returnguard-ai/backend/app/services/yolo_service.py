"""YOLO object-detection service (Ultralytics).

Design:
- The model is loaded ONCE (lazy singleton with a lock), never per request.
- Weights, confidence threshold and device come from settings and are validated.
- Missing/incompatible weights produce MODEL_UNAVAILABLE / FAILED statuses with
  a clear error; detections are NEVER fabricated.
- Bounding boxes are clamped to image bounds and validated (x2>x1, y2>y1).

Limitations (surfaced to the UI): a generic COCO-pretrained model (yolov8n.pt)
cannot validate specific product variants, small accessories, missing components
or defects. Custom labeled weights are required for those tasks.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("returnguard.yolo")

GENERIC_MODEL_HINT = (
    "Generic COCO-pretrained weights cannot confirm product variants, small "
    "accessories, missing components or defects. Provide custom labeled weights "
    "for return-inspection claims."
)


@dataclass
class DetectionItem:
    class_id: int
    class_label: str
    confidence: float
    bbox: list[float]


@dataclass
class DetectionData:
    status: str
    model_name: str = ""
    model_path: str = ""
    device: str = ""
    confidence_threshold: float = 0.35
    inference_ms: int = 0
    detections: list[DetectionItem] = field(default_factory=list)
    error: str | None = None
    notes: list[str] = field(default_factory=list)


_model = None
_model_lock = threading.Lock()
_model_path_loaded: str | None = None


def _resolve_device() -> str:
    requested = settings.yolo_device.strip().lower()
    if requested != "auto":
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def get_model_info() -> dict:
    """Cheap availability report for the health endpoint (no heavy import)."""
    path = settings.yolo_model_path
    exists = Path(path).exists()
    return {
        "configured_model_path": path,
        "weights_present": exists,
        "confidence_threshold": settings.yolo_confidence_threshold,
        "device": settings.yolo_device,
        "loaded": _model is not None,
    }


def _load_model():
    global _model, _model_path_loaded
    if _model is not None and _model_path_loaded == settings.yolo_model_path:
        return _model
    with _model_lock:
        if _model is not None and _model_path_loaded == settings.yolo_model_path:
            return _model
        from ultralytics import YOLO  # heavy import, done once

        path = settings.yolo_model_path
        if not Path(path).exists() and not str(path).lower().endswith((".pt", ".onnx")):
            raise FileNotFoundError(f"YOLO weights not found: {path}")
        model = YOLO(str(path))  # loads/validates weights; may auto-download yolov8n.pt
        # Force an internal weights sanity check early.
        if not hasattr(model, "names"):
            raise ValueError("Loaded YOLO model has no class names metadata")
        _model = model
        _model_path_loaded = path
        logger.info("YOLO model loaded: %s device=%s", path, _resolve_device())
        return model


def _clamp_bbox(bbox, width: int, height: int) -> list[float] | None:
    x1, y1, x2, y2 = (float(v) for v in bbox)
    x1 = max(0.0, min(x1, width - 1))
    x2 = max(0.0, min(x2, width - 1))
    y1 = max(0.0, min(y1, height - 1))
    y2 = max(0.0, min(y2, height - 1))
    if x2 - x1 < 1 or y2 - y1 < 1:
        return None
    return [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)]


def _infer(image_path: Path, conf: float, device: str) -> tuple[list[DetectionItem], str, int, str]:
    model = _load_model()
    started = time.perf_counter()
    results = model.predict(str(image_path), conf=conf, device=device, verbose=False)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    names = model.names
    detections: list[DetectionItem] = []
    if results:
        r = results[0]
        width, height = int(r.orig_shape[1]), int(r.orig_shape[0])
        boxes = getattr(r, "boxes", None)
        if boxes is not None and len(boxes):
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                score = float(boxes.conf[i].item())
                xyxy = boxes.xyxy[i].tolist()
                bbox = _clamp_bbox(xyxy, width, height)
                if bbox is None:
                    continue
                label = str(names.get(cls_id, cls_id)) if isinstance(names, dict) else str(names[cls_id])
                detections.append(
                    DetectionItem(class_id=cls_id, class_label=label, confidence=round(score, 4), bbox=bbox)
                )
    return detections, device, elapsed_ms, str(getattr(model, "ckpt_path", "") or settings.yolo_model_path)


def run_detection(image_path: Path) -> DetectionData:
    """Run real YOLO inference or report why it could not run."""
    conf = settings.yolo_confidence_threshold
    device = _resolve_device()
    model_path = settings.yolo_model_path

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_infer, image_path, conf, device)
            detections, device_used, elapsed_ms, resolved_path = future.result(
                timeout=settings.yolo_timeout_seconds
            )
    except FuturesTimeout:
        return DetectionData(
            status="TIMEOUT",
            model_path=model_path,
            device=device,
            confidence_threshold=conf,
            error=f"YOLO inference exceeded the {settings.yolo_timeout_seconds}s timeout.",
        )
    except FileNotFoundError as exc:
        return DetectionData(
            status="MODEL_UNAVAILABLE",
            model_path=model_path,
            device=device,
            confidence_threshold=conf,
            error=str(exc),
        )
    except Exception as exc:
        logger.exception("YOLO inference failed")
        return DetectionData(
            status="FAILED",
            model_path=model_path,
            device=device,
            confidence_threshold=conf,
            error=f"YOLO inference failed ({type(exc).__name__}): {exc}"[:500],
        )

    model_name = Path(resolved_path).name
    notes: list[str] = []
    if model_name.lower().startswith(("yolov8", "yolov5", "yolo11")) and any(
        model_name.lower().startswith(p) for p in ("yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x", "yolov5n", "yolov5s")
    ):
        notes.append(GENERIC_MODEL_HINT)
    return DetectionData(
        status="OK",
        model_name=model_name,
        model_path=resolved_path,
        device=device_used,
        confidence_threshold=conf,
        inference_ms=elapsed_ms,
        detections=detections,
        notes=notes,
    )
