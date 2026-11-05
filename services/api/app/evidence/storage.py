import os
import uuid
from pathlib import Path

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".txt", ".doc", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class LocalStorage:
    def __init__(self, base_dir=None):
        raw = base_dir or os.getenv("UPLOAD_DIR", "uploads")
        self.base_dir = Path(raw).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, file_stream, original_name):
        ext = Path(original_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return None, "invalid_extension"
        file_stream.seek(0, os.SEEK_END)
        size = file_stream.tell()
        file_stream.seek(0)
        if size > MAX_FILE_SIZE:
            return None, "file_too_large"
        stored_name = f"{uuid.uuid4().hex}{ext}"
        dest = self.base_dir / stored_name
        file_stream.save(str(dest))
        return stored_name, None

    def load(self, stored_name):
        path = self.base_dir / stored_name
        if not path.exists():
            return None
        return path

    def delete(self, stored_name):
        path = self.base_dir / stored_name
        if path.exists():
            path.unlink()


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage
