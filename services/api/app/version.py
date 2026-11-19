"""Version centralizada de SIGOS (Fase 2, O6).

Fuente unica: el archivo ``services/api/VERSION``. El commit se toma de
``SIGOS_COMMIT`` (inyectado en build/CI) y, si no existe, del directorio .git
local; fuera de un repositorio (p. ej. imagen Docker sin SIGOS_COMMIT) es None.
"""
import os
import re
from functools import lru_cache
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = API_ROOT / "VERSION"
_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")


@lru_cache(maxsize=1)
def get_version():
    try:
        value = VERSION_FILE.read_text(encoding="utf-8").strip()
        return value or "0.0.0-unknown"
    except OSError:
        return "0.0.0-unknown"


def _commit_from_git():
    for base in (API_ROOT, *API_ROOT.parents):
        git_dir = base / ".git"
        if not git_dir.is_dir():
            continue
        try:
            head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
            if not head.startswith("ref:"):
                return head
            ref = head[4:].strip()
            ref_file = git_dir / ref
            if ref_file.is_file():
                return ref_file.read_text(encoding="utf-8").strip()
            packed = git_dir / "packed-refs"
            if packed.is_file():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    parts = line.split()
                    if len(parts) == 2 and parts[1] == ref:
                        return parts[0]
        except OSError:
            return None
        return None
    return None


@lru_cache(maxsize=1)
def get_commit():
    """SHA corto (12) o None. Solo se aceptan valores hexadecimales."""
    raw = (os.getenv("SIGOS_COMMIT") or "").strip() or _commit_from_git()
    if raw and _SHA.match(raw):
        return raw[:12].lower()
    return None
