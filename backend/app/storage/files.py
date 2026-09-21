"""
Private file storage for uploaded documents (Sprint 12).

Design decisions:

- **Nothing uploaded is ever executed or served as-is.** Files are
  written under `UPLOAD_DIR` with a random name and a fixed extension
  chosen by us from the detected type, never from the uploaded filename.
  They're returned only by an endpoint that checks permissions first.
- **The type is decided by the file's own first bytes**, not by the
  `Content-Type` header or the extension, both of which the uploader
  controls. Only PDF, JPEG, PNG and WebP are accepted.
- **The size is capped while reading**, in chunks, so a huge upload is
  rejected instead of being buffered into memory or the disk first.
- `stored_path` is always relative to `UPLOAD_DIR`, so the storage root
  can differ between environments (and later become object storage
  without touching the database).
"""

import re
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError

# (extension, media type) by magic bytes. WebP needs a second check at byte 8.
_SIGNATURES: list[tuple[bytes, str, str]] = [
    (b"%PDF-", ".pdf", "application/pdf"),
    (b"\xff\xd8\xff", ".jpg", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", ".png", "image/png"),
]
ALLOWED_DESCRIPTION = "PDF, JPEG, PNG or WebP"
CHUNK = 64 * 1024


def _detect(head: bytes) -> tuple[str, str] | None:
    for magic, extension, media_type in _SIGNATURES:
        if head.startswith(magic):
            return extension, media_type
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None


def upload_root() -> Path:
    settings = get_settings()
    root = Path(settings.upload_dir)
    if not root.is_absolute():
        # backend/app/storage/files.py -> backend/
        root = Path(__file__).resolve().parents[2] / root
    return root


def safe_filename(name: str) -> str:
    """The uploader's name, kept only for display: no paths, no control characters."""
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip() or "document"
    return name[:255]


def save_upload(stream: BinaryIO, *, folder: str) -> tuple[str, str, int]:
    """
    Writes an uploaded stream into `UPLOAD_DIR/<folder>/<random><ext>`.

    Returns (relative path, detected media type, size in bytes). Raises
    ValidationAppError for an empty file, an unsupported type, or one
    over MAX_UPLOAD_MB — nothing is left on disk in those cases.
    """
    limit = get_settings().max_upload_mb * 1024 * 1024
    head = stream.read(CHUNK)
    if not head:
        raise ValidationAppError("The file is empty")
    detected = _detect(head)
    if detected is None:
        raise ValidationAppError(f"Unsupported file type. Please upload {ALLOWED_DESCRIPTION}.")
    extension, media_type = detected

    relative = f"{folder}/{uuid.uuid4().hex}{extension}"
    destination = upload_root() / relative
    destination.parent.mkdir(parents=True, exist_ok=True)

    size = 0
    chunk = head
    try:
        with destination.open("wb") as out:
            while chunk:
                size += len(chunk)
                if size > limit:
                    raise ValidationAppError(f"The file is larger than {get_settings().max_upload_mb} MB")
                out.write(chunk)
                chunk = stream.read(CHUNK)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return relative, media_type, size


def resolve(relative_path: str) -> Path:
    """Absolute path of a stored file, guarding against paths that escape the root."""
    root = upload_root().resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValidationAppError("Invalid file path")
    return path


def delete(relative_path: str) -> None:
    resolve(relative_path).unlink(missing_ok=True)
