# -*- coding: utf-8 -*-
import hashlib
import io
import os
import re
import secrets
import uuid
from pathlib import Path

from PIL import Image

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "application/pdf",
}

MAGIC_SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF", "application/pdf"),
    (b"RIFF", "image/webp"),  # refined below
]


def _detect_mime(data):
    for sig, mime in MAGIC_SIGNATURES:
        if data.startswith(sig):
            if mime == "image/webp":
                if len(data) >= 12 and data[8:12] == b"WEBP":
                    return "image/webp"
                continue
            return mime
    return None


def _read_input(file_input, original_name=None):
    name = original_name
    if hasattr(file_input, "read"):
        data = file_input.read()
        if hasattr(file_input, "seek"):
            try:
                file_input.seek(0)
            except Exception:
                pass
        if name is None and getattr(file_input, "filename", None):
            name = file_input.filename
        if name is None and getattr(file_input, "name", None):
            name = file_input.name
    elif isinstance(file_input, (bytes, bytearray)):
        data = bytes(file_input)
    else:
        data = bytes(file_input)
    if name is None:
        name = "upload.bin"
    return data, name


class LocalStorage:
    def __init__(self, base_dir=None, max_file_size=None, allowed_mime_types=None):
        raw = base_dir or os.getenv("EVIDENCE_UPLOAD_DIR") or os.getenv("UPLOAD_DIR", "uploads")
        self.base_dir = Path(raw).resolve()
        self.originals_dir = self.base_dir / "originals"
        self.derivatives_dir = self.base_dir / "derivatives"
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        self.derivatives_dir.mkdir(parents=True, exist_ok=True)
        if max_file_size is None:
            max_file_size = int(os.getenv("EVIDENCE_MAX_FILE_SIZE", str(10 * 1024 * 1024)))
        self.max_file_size = int(max_file_size)
        if allowed_mime_types is None:
            env = os.getenv("EVIDENCE_ALLOWED_MIME_TYPES")
            if env:
                allowed_mime_types = {x.strip() for x in env.split(",") if x.strip()}
            else:
                allowed_mime_types = ALLOWED_MIME_TYPES
        self.allowed_mime_types = set(allowed_mime_types)

    def _safe_key(self, key):
        if not key or not isinstance(key, str):
            return None
        if "/" in key or "\\" in key or ".." in key:
            return None
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            return None
        return key

    def validate(self, file_input, original_name=None, declared_mime=None):
        data, name = _read_input(file_input, original_name)
        if not data:
            return None, 0, None, "empty_file"
        size = len(data)
        if size > self.max_file_size:
            return None, size, None, "file_too_large"
        mime = _detect_mime(data)
        if mime is None:
            return None, size, None, "unknown_content_type"
        if mime not in self.allowed_mime_types:
            return None, size, None, "mime_not_allowed"
        if mime.startswith("image/"):
            try:
                img = Image.open(io.BytesIO(data))
                img.verify()
            except Exception:
                return None, size, None, "invalid_image"
        if mime == "application/pdf":
            if not data.startswith(b"%PDF"):
                return None, size, None, "invalid_pdf"
        sha256 = hashlib.sha256(data).hexdigest()
        return mime, size, sha256, None

    def save(self, file_input, original_name=None, declared_mime=None):
        data, name = _read_input(file_input, original_name)
        mime, size, sha256, error = self.validate(data, name, declared_mime)
        if error:
            return None, None, error
        key = secrets.token_urlsafe(32).replace("-", "_").replace("+", "")
        # ensure filesystem-safe token (token_urlsafe already safe)
        key = uuid.uuid4().hex + secrets.token_hex(8)
        dest = self.originals_dir / key
        dest.write_bytes(data)
        metadata = {
            "original_name": name,
            "mime_type": mime,
            "size_bytes": size,
            "sha256": sha256,
            "storage_key": key,
        }
        return key, metadata, None

    def save_bytes(self, data, original_name=None, declared_mime=None):
        return self.save(data, original_name, declared_mime)

    def store(self, *args, **kwargs):
        return self.save(*args, **kwargs)

    def upload(self, *args, **kwargs):
        return self.save(*args, **kwargs)

    def load(self, storage_key, variant="original"):
        key = self._safe_key(storage_key)
        if not key:
            return None
        if variant == "derivative":
            path = self.derivatives_dir / key
        else:
            path = self.originals_dir / key
        if not path.exists() or not path.is_file():
            # legacy flat path
            legacy = self.base_dir / key
            if legacy.exists() and legacy.is_file():
                return legacy
            return None
        return path

    def delete(self, storage_key):
        key = self._safe_key(storage_key)
        if not key:
            return False
        removed = False
        for d in (self.originals_dir, self.derivatives_dir, self.base_dir):
            path = d / key
            if path.exists() and path.is_file():
                try:
                    path.unlink()
                    removed = True
                except OSError:
                    pass
        return removed

    def exists(self, storage_key):
        return self.load(storage_key) is not None

    def metadata(self, storage_key):
        path = self.load(storage_key)
        if not path:
            return None
        data = path.read_bytes()
        return {
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage


def reset_storage():
    global _storage
    _storage = None
