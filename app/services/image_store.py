"""Image attachment storage helper.

Validates uploaded image bytes, resizes them to fit within
``settings.image_max_dimension`` (preserving aspect ratio), re-encodes as JPEG
to drop any EXIF metadata, and writes to a content-addressable path on disk.

The caller (upload router) persists the returned ``file_path`` and ``file_hash``
in the ``attachments`` table.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import settings

logger = logging.getLogger(__name__)

# Decompression-bomb defence. Pillow raises if the decoded image would exceed
# this. 64 megapixels is well above any realistic 1568×1568 final, but stops
# attackers from feeding tiny gzipped images that explode in memory.
Image.MAX_IMAGE_PIXELS = 64_000_000

_ALLOWED_FORMATS: frozenset[str] = frozenset({"PNG", "JPEG", "WEBP"})


class ImageStoreError(RuntimeError):
    """Raised when an upload is not a usable image."""


def resize_and_save(file_bytes: bytes, dest_dir: Path) -> dict[str, object]:
    """Validate, resize, and persist ``file_bytes`` under ``dest_dir``.

    Returns a metadata dict with ``file_hash``, ``file_path`` (relative to
    cwd), ``mime_type``, ``width``, ``height``, ``byte_size``. The output is
    always JPEG so the metadata is constant across input formats and EXIF is
    stripped (Pillow re-encodes from RGB pixels).
    """
    try:
        verifier = Image.open(io.BytesIO(file_bytes))
        verifier.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageStoreError(f"Invalid image: {exc}") from exc

    try:
        img = Image.open(io.BytesIO(file_bytes))
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageStoreError(f"Could not reopen image: {exc}") from exc

    if img.format not in _ALLOWED_FORMATS:
        raise ImageStoreError(
            f"Unsupported format: {img.format} (expected one of {sorted(_ALLOWED_FORMATS)})"
        )

    img = img.convert("RGB")
    max_dim = settings.image_max_dimension
    img.thumbnail((max_dim, max_dim))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, optimize=True)
    out_bytes = buf.getvalue()

    file_hash = hashlib.sha256(out_bytes).hexdigest()
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_path = dest_dir / f"{file_hash}.jpg"
    if not file_path.exists():
        file_path.write_bytes(out_bytes)

    try:
        rel_path = file_path.relative_to(Path.cwd())
    except ValueError:
        rel_path = file_path

    return {
        "file_hash": file_hash,
        "file_path": str(rel_path),
        "mime_type": "image/jpeg",
        "width": img.width,
        "height": img.height,
        "byte_size": len(out_bytes),
    }


def load_image_b64(file_path: str) -> str:
    """Read the saved JPEG and return a ``data:image/jpeg;base64,…`` URL."""
    raw = Path(file_path).read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


def remove_image_file(file_path: str) -> bool:
    """Delete the on-disk file. Returns True if removed, False if missing."""
    p = Path(file_path)
    if not p.exists():
        return False
    p.unlink()
    return True
