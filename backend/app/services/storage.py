"""File storage: upload validation (magic bytes, size), SHA-256, and short-lived file links.

Files are never served by path. A caller who is allowed to see a document asks for a link;
the link carries a signed token that expires after `file_link_expire_seconds`.
"""
import hashlib
from datetime import timedelta
from pathlib import Path

import jwt

from app.config import settings
from app.models.base import utcnow

# (magic prefix, mime type, file extension)
_MAGIC = [
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
]


class UploadRejected(ValueError):
    pass


def detect_type(data: bytes) -> tuple[str, str]:
    """Return (mime, extension) from magic bytes, ignoring the client's filename / content-type."""
    for magic, mime, ext in _MAGIC:
        if data.startswith(magic):
            return mime, ext
    raise UploadRejected("Unsupported file type. Allowed: PDF, PNG, JPEG.")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_upload(data: bytes) -> tuple[str, str]:
    if not data:
        raise UploadRejected("File is empty.")
    if len(data) > settings.max_upload_bytes:
        raise UploadRejected(f"File is larger than {settings.max_upload_bytes // (1024 * 1024)} MB.")
    return detect_type(data)


def save_file(data: bytes, doc_id: str, ext: str) -> str:
    """Write the file under storage_dir and return its path relative to storage_dir."""
    rel = Path(doc_id[:2]) / f"{doc_id}{ext}"
    full = Path(settings.storage_dir) / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data)
    return rel.as_posix()


def full_path(rel_path: str) -> Path:
    return Path(settings.storage_dir) / rel_path


def create_file_token(doc_id: str, user_id: str) -> str:
    claims = {"typ": "file", "doc": doc_id, "sub": user_id,
              "exp": utcnow() + timedelta(seconds=settings.file_link_expire_seconds)}
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def read_file_token(token: str) -> dict | None:
    """Claims if the token is a valid, unexpired file token; else None."""
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError:
        return None
    return claims if claims.get("typ") == "file" else None
