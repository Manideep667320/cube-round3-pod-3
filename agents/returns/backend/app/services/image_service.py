"""Image validation and controlled storage.

- Decoding uses Pillow; corrupt or unsupported files are rejected.
- Stored filenames are generated server-side UUIDs (never client filenames).
- Only metadata is kept in the database; binaries live under STORAGE_DIR.
"""
from __future__ import annotations

import hashlib
import io
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from agents.returns.backend.app.core.config import settings
from agents.returns.backend.app.core.errors import AppError, NotFoundError, PayloadTooLargeError

# Guard against decompression bombs.
Image.MAX_IMAGE_PIXELS = 60_000_000

_FORMAT_TO_EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp"}


@dataclass
class StoredImage:
    stored_name: str
    path: Path
    content_type: str
    original_name: str
    size_bytes: int
    sha256: str
    width: int
    height: int
    image_format: str


def _sanitize_original_name(name: str) -> str:
    base = Path(name or "upload").name
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base)
    return base[:200] or "upload"


def validate_and_store(data: bytes, return_id: str, original_name: str) -> StoredImage:
    if not data:
        raise AppError("The uploaded file is empty.", code="empty_file")
    if len(data) > settings.max_upload_bytes:
        raise PayloadTooLargeError(
            f"File exceeds the {settings.max_upload_mb} MB limit.", code="file_too_large"
        )

    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()  # verify() checks integrity without fully decoding
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise AppError(
            "The file is not a valid, supported image (JPEG, PNG, WEBP or BMP).",
            code="invalid_image",
        ) from exc

    # Full decode after verify() to catch truncation and to read dimensions.
    try:
        with Image.open(io.BytesIO(data)) as img:
            img_format = (img.format or "").upper()
            width, height = img.size
            img.load()
    except (OSError, Image.DecompressionBombError) as exc:
        raise AppError("The image file appears to be corrupt.", code="corrupt_image") from exc

    if img_format not in settings.allowed_formats_set or img_format not in _FORMAT_TO_EXT:
        raise AppError(
            f"Unsupported image format '{img_format or 'unknown'}'. Allowed: JPEG, PNG, WEBP, BMP.",
            code="unsupported_format",
        )
    if width < 32 or height < 32:
        raise AppError("The image is too small to inspect (minimum 32x32 pixels).", code="image_too_small")

    ext = _FORMAT_TO_EXT[img_format]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest_dir = Path(settings.storage_dir) / return_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / stored_name
    dest.write_bytes(data)

    content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "BMP": "image/bmp"}[img_format]
    return StoredImage(
        stored_name=stored_name,
        path=dest,
        content_type=content_type,
        original_name=_sanitize_original_name(original_name),
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        width=width,
        height=height,
        image_format=img_format,
    )


def resolve_stored_path(return_id: str, stored_name: str) -> Path:
    """Resolve a stored image path, rejecting traversal attempts."""
    if "/" in stored_name or "\\" in stored_name or ".." in stored_name:
        raise NotFoundError("Image not found.", code="image_not_found")
    path = Path(settings.storage_dir) / return_id / stored_name
    if not path.is_file():
        raise NotFoundError("Image not found.", code="image_not_found")
    return path
