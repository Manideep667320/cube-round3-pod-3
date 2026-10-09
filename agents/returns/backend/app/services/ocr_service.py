"""OCR service running a real OCR engine on uploaded images.

Engine selection (OCR_ENGINE):
- rapidocr : RapidOCR (PP-OCRv4 models via onnxruntime) - default, self-contained.
- tesseract: pytesseract + a locally installed Tesseract binary.
- none     : OCR disabled explicitly.
- auto     : prefer rapidocr if importable, else tesseract, else report unavailable.

Statuses are honest: OK / NO_TEXT_DETECTED / LOW_CONFIDENCE / ENGINE_UNAVAILABLE /
TIMEOUT / FAILED. This service never invents text or confidence values.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from pathlib import Path

from agents.returns.backend.app.core.config import settings

logger = logging.getLogger("returnguard.ocr")


@dataclass
class OCRBlock:
    text: str
    confidence: float | None
    box: list[list[float]] | None


@dataclass
class OCRData:
    engine: str
    engine_version: str
    status: str
    full_text: str = ""
    mean_confidence: float | None = None
    blocks: list[OCRBlock] = field(default_factory=list)
    processing_ms: int = 0
    error: str | None = None


_engine_lock = threading.Lock()
_engine = None
_engine_name = ""
_engine_version = ""


def _try_load_rapidocr():
    from rapidocr_onnxruntime import RapidOCR  # type: ignore

    engine = RapidOCR()
    version = ""
    try:
        import rapidocr_onnxruntime as _pkg

        version = getattr(_pkg, "__version__", "") or ""
    except Exception:  # pragma: no cover
        pass
    return engine, version


def _try_load_tesseract():
    import pytesseract  # type: ignore

    version = pytesseract.get_tesseract_version()
    return pytesseract, str(version)


def get_engine_info() -> dict:
    """Report OCR availability without loading heavy models."""
    engine = settings.ocr_engine
    info: dict = {"configured_engine": engine, "available": False, "engine": None, "version": ""}
    if engine == "none":
        return info
    try:
        if engine in ("auto", "rapidocr"):
            import rapidocr_onnxruntime  # noqa: F401

            info.update({"available": True, "engine": "rapidocr"})
            return info
    except Exception:
        pass
    try:
        if engine in ("auto", "tesseract"):
            import pytesseract  # noqa: F401

            info.update({"available": True, "engine": "tesseract"})
            return info
    except Exception:
        pass
    return info


def _get_engine():
    global _engine, _engine_name, _engine_version
    if _engine is not None:
        return _engine, _engine_name, _engine_version
    with _engine_lock:
        if _engine is not None:
            return _engine, _engine_name, _engine_version
        wanted = settings.ocr_engine
        errors: list[str] = []
        if wanted in ("auto", "rapidocr"):
            try:
                _engine, _engine_version = _try_load_rapidocr()
                _engine_name = "rapidocr"
                return _engine, _engine_name, _engine_version
            except Exception as exc:  # pragma: no cover - depends on host env
                errors.append(f"rapidocr: {type(exc).__name__}")
                if wanted == "rapidocr":
                    logger.error("RapidOCR requested but unavailable: %s", errors)
                    return None, "rapidocr", ""
        if wanted in ("auto", "tesseract"):
            try:
                _engine, _engine_version = _try_load_tesseract()
                _engine_name = "tesseract"
                return _engine, _engine_name, _engine_version
            except Exception as exc:
                errors.append(f"tesseract: {type(exc).__name__}")
        logger.warning("No OCR engine available (%s)", ", ".join(errors) or "disabled")
        return None, wanted, ""


def _run_rapidocr(engine, image_path: Path) -> list[OCRBlock]:
    import cv2  # provided by ultralytics/opencv

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError("OpenCV could not decode the image")
    result, _elapse = engine(img)
    blocks: list[OCRBlock] = []
    for item in result or []:
        box, text, conf = item[0], item[1], item[2]
        points = [[float(x), float(y)] for x, y in box]
        blocks.append(OCRBlock(text=str(text), confidence=round(float(conf) * 100.0, 2), box=points))
    return blocks


def _run_tesseract(engine, image_path: Path) -> list[OCRBlock]:
    import pytesseract  # type: ignore
    from PIL import Image

    with Image.open(image_path) as img:
        data = engine.image_to_data(img, output_type=pytesseract.Output.DICT)
    blocks: list[OCRBlock] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = None
        if conf is not None and conf < 0:
            conf = None
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        box = [[float(x), float(y)], [float(x + w), float(y)], [float(x + w), float(y + h)], [float(x), float(y + h)]]
        blocks.append(OCRBlock(text=text, confidence=None if conf is None else round(conf, 2), box=box))
    return blocks


def _extract(image_path: Path) -> tuple[list[OCRBlock], str, str]:
    engine, name, version = _get_engine()
    if engine is None:
        raise LookupError("no-engine")
    if name == "rapidocr":
        return _run_rapidocr(engine, image_path), name, version
    return _run_tesseract(engine, image_path), name, version


def run_ocr(image_path: Path) -> OCRData:
    """Run real OCR and return honest results with distinct statuses."""
    started = time.perf_counter()

    info = get_engine_info()
    if settings.ocr_engine == "none" or not info["available"]:
        return OCRData(
            engine=settings.ocr_engine,
            engine_version="",
            status="ENGINE_UNAVAILABLE",
            processing_ms=0,
            error="No OCR engine is installed/configured. Install rapidocr-onnxruntime or Tesseract.",
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_extract, image_path)
            blocks, name, version = future.result(timeout=settings.ocr_timeout_seconds)
    except FuturesTimeout:
        return OCRData(
            engine=settings.ocr_engine,
            engine_version="",
            status="TIMEOUT",
            processing_ms=int((time.perf_counter() - started) * 1000),
            error=f"OCR exceeded the {settings.ocr_timeout_seconds}s timeout.",
        )
    except LookupError:
        return OCRData(
            engine=settings.ocr_engine,
            engine_version="",
            status="ENGINE_UNAVAILABLE",
            error="The configured OCR engine failed to load.",
        )
    except Exception as exc:
        logger.exception("OCR failed for %s", image_path.name)
        return OCRData(
            engine=settings.ocr_engine,
            engine_version="",
            status="FAILED",
            processing_ms=int((time.perf_counter() - started) * 1000),
            error=f"OCR processing failed ({type(exc).__name__}).",
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if not blocks:
        return OCRData(
            engine=name, engine_version=version, status="NO_TEXT_DETECTED",
            full_text="", mean_confidence=None, blocks=[], processing_ms=elapsed_ms,
        )

    full_text = "\n".join(b.text for b in blocks)
    confidences = [b.confidence for b in blocks if b.confidence is not None]
    mean_conf = round(sum(confidences) / len(confidences), 2) if confidences else None
    status = "OK"
    if mean_conf is not None and mean_conf < settings.ocr_low_confidence_threshold:
        status = "LOW_CONFIDENCE"
    return OCRData(
        engine=name, engine_version=version, status=status, full_text=full_text,
        mean_confidence=mean_conf, blocks=blocks, processing_ms=elapsed_ms,
    )
