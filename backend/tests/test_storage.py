import hashlib

import pytest

from app.config import settings
from app.services import storage


def test_magic_bytes_decide_type_not_filename():
    assert storage.detect_type(b"%PDF-1.7 ...") == ("application/pdf", ".pdf")
    assert storage.detect_type(b"\x89PNG\r\n\x1a\n....")[0] == "image/png"
    assert storage.detect_type(b"\xff\xd8\xff\xe0....")[0] == "image/jpeg"
    with pytest.raises(storage.UploadRejected):
        storage.detect_type(b"MZ\x90\x00 an exe renamed to .pdf")


def test_size_limit_and_empty(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    with pytest.raises(storage.UploadRejected, match="larger"):
        storage.validate_upload(b"%PDF-" + b"x" * 20)
    with pytest.raises(storage.UploadRejected, match="empty"):
        storage.validate_upload(b"")


def test_save_and_sha256():
    data = b"%PDF-1.4 hello"
    rel = storage.save_file(data, "abcdef-123", ".pdf")
    assert storage.full_path(rel).read_bytes() == data
    assert storage.sha256_hex(data) == hashlib.sha256(data).hexdigest()


def test_file_token_roundtrip_and_expiry(monkeypatch):
    token = storage.create_file_token("doc-1", "user-1")
    assert storage.read_file_token(token)["doc"] == "doc-1"
    assert storage.read_file_token(token + "x") is None
    monkeypatch.setattr(settings, "file_link_expire_seconds", -1)
    assert storage.read_file_token(storage.create_file_token("doc-1", "user-1")) is None


def test_file_token_cannot_be_used_to_log_in(client):
    token = storage.create_file_token("doc-1", "user-1")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
