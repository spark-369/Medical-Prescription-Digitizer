"""File upload validation and local-filesystem storage helpers."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import UploadValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)


def validate_upload(*, filename: str, content_type: str, size: int) -> str:
    """Validate an uploaded file; returns the normalized file suffix."""
    settings = get_settings()
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.allowed_upload_extensions:
        allowed = ", ".join(settings.allowed_upload_extensions)
        raise UploadValidationError(f"Unsupported file type '{suffix}'. Allowed: {allowed}")
    if content_type not in settings.allowed_upload_content_types:
        allowed = ", ".join(settings.allowed_upload_content_types)
        raise UploadValidationError(
            f"Unsupported content type '{content_type}'. Allowed: {allowed}"
        )
    # Minimum floor keeps empty/noise uploads out (a real prescription image
    # is at least a few KB); it also covers the zero-byte case.
    min_bytes = settings.min_upload_size_kb * 1024
    if size < min_bytes:
        raise UploadValidationError(
            f"File is too small — minimum size is {settings.min_upload_size_kb} KB"
        )
    # Strict upper bound: accepted files must be *smaller than* the cap.
    # Set max_upload_size_mb = 0 to disable the upper bound.
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if settings.max_upload_size_mb > 0 and size >= max_bytes:
        raise UploadValidationError(
            f"File must be smaller than {settings.max_upload_size_mb} MB"
        )
    return suffix


def save_upload(data: bytes, suffix: str) -> tuple[str, str, str]:
    """Persist bytes under ``upload_dir/YYYY/MM/<uuid>.<ext>``.

    Returns ``(relative_path, absolute_path, sha256)``. Only the relative
    path is stored in the database so the storage root stays relocatable.
    """
    root = get_settings().resolved_upload_dir
    now = datetime.now(UTC)
    subdir = root / now.strftime("%Y") / now.strftime("%m")
    subdir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{suffix}"
    path = subdir / name
    path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    return str(path.relative_to(root)), str(path), digest


def delete_stored_file(stored_path: str) -> None:
    path = get_settings().resolved_upload_dir / stored_path
    try:
        path.unlink(missing_ok=True)
    except OSError:  # pragma: no cover - best effort cleanup
        logger.warning("Could not delete stored file %s", path)
