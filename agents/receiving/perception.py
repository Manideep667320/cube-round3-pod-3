"""W2 perception: deterministic image quality (OpenCV) and barcode decoding (zxing-cpp).

No model calls here. Everything in this module is reproducible from the pixels,
which is what makes `decide()` testable and evaluation reproducible.

Quality flags (IMG_BLURRY / IMG_GLARE / IMG_DARK) are DIAGNOSTIC only: decide()
raises them as the *cause* of NO_BARCODE / LOW_CONF_DAMAGE, never as a verdict
on their own (plan section 4, test 11).
"""
from __future__ import annotations

from . import config

import cv2
import numpy as np
import zxingcpp

QUALITY_FLAGS = ("IMG_BLURRY", "IMG_GLARE", "IMG_DARK")


def load_image(path: str) -> np.ndarray | None:
    """Read a file from disk as BGR, or None if it is not a decodable image."""
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return img


def compute_quality(img: np.ndarray, thresholds: dict | None = None) -> dict:
    """Laplacian variance (blur), bright-pixel ratio (glare), mean luminance."""
    th = thresholds or config.thresholds()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    glare = float((gray > th["glare_pixel_value"]).mean())
    luminance = float(gray.mean())

    flags = []
    if blur < th["blur_min_variance"]:
        flags.append("IMG_BLURRY")
    if glare > th["glare_max_ratio"]:
        flags.append("IMG_GLARE")
    if luminance < th["lum_min"] or luminance > th["lum_max"]:
        flags.append("IMG_DARK")

    return {"blur": round(blur, 1), "glare": round(glare, 4),
            "luminance": round(luminance, 1), "flags": flags}


def _variants(img: np.ndarray) -> list[np.ndarray]:
    """Original first, then an upscaled+sharpened grayscale pass for small/faded codes."""
    out = [img]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    big = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    sharpened = cv2.addWeighted(big, 1.8, cv2.GaussianBlur(big, (0, 0), 1.2), -0.8, 0)
    out.append(cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR))
    return out


def decode_barcode(img: np.ndarray) -> dict:
    """Try zxing-cpp on each variant; first hit wins (plan: label first, caller orders photos)."""
    for variant in _variants(img):
        try:
            results = zxingcpp.read_barcodes(variant)
        except Exception:
            continue
        if results:
            hit = results[0]
            return {"found": True, "value": hit.text, "format": str(getattr(hit, "format", ""))}
    return {"found": False, "value": None, "format": None}


def analyse_photo(path: str, thresholds: dict | None = None) -> tuple[dict, dict]:
    """(quality, barcode) for one image file. Raises FileNotFoundError / ValueError upstream."""
    img = load_image(path)
    if img is None:
        raise ValueError(f"unreadable image: {path}")
    return compute_quality(img, thresholds), decode_barcode(img)
