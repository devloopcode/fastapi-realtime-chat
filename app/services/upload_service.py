"""
Upload service — handles image file validation and storage.

Structure is S3-ready: swap _save_local() with an S3 put_object call
and update generate_url() without changing any callers.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

_MAX_BYTES = settings.max_file_size_mb * 1024 * 1024


async def save_upload(file: UploadFile) -> str:
    """Validate, save, and return the public URL path of an uploaded image."""
    _validate_content_type(file.content_type)
    data = await file.read()
    _validate_size(len(data))
    _validate_magic_bytes(data, file.content_type)

    ext = _extension(file.content_type)
    filename = f"{uuid.uuid4()}{ext}"
    dest = Path(settings.upload_dir) / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(dest, "wb") as f:
        await f.write(data)

    url = f"/uploads/images/{filename}"
    logger.info("image_uploaded", filename=filename, size=len(data))
    return url


def _validate_content_type(content_type: str | None) -> None:
    if content_type not in settings.allowed_image_types:
        raise ValidationError(
            f"Unsupported file type. Allowed: {', '.join(settings.allowed_image_types)}"
        )


def _validate_size(size: int) -> None:
    if size > _MAX_BYTES:
        raise ValidationError(f"File too large. Maximum size is {settings.max_file_size_mb} MB")


def _validate_magic_bytes(data: bytes, content_type: str) -> None:
    """Check file magic bytes to prevent content-type spoofing."""
    signatures: dict[str, list[bytes]] = {
        "image/jpeg": [b"\xff\xd8\xff"],
        "image/png": [b"\x89PNG"],
        "image/gif": [b"GIF87a", b"GIF89a"],
        "image/webp": [b"RIFF"],
    }
    allowed_sigs = signatures.get(content_type, [])
    if allowed_sigs and not any(data.startswith(sig) for sig in allowed_sigs):
        raise ValidationError("File content does not match declared type")


def _extension(content_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(content_type, ".bin")
