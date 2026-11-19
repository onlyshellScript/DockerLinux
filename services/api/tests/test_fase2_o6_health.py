# Fase 2 / O6: version centralizada, health ampliado compatible y /health/live sin BD.
import json
import re

import pytest
from sqlalchemy.exc import OperationalError

from app import version as version_mod
from app.health import service as health_service
from app.version import VERSION_FILE, get_commit, get_version


@pytest.fixture(autouse=True)
def _clear_caches():
    get_version.cache_clear()
    get_commit.cache_clear()
    yield
    get_version.cache_clear()
    get_commit.cache_clear()


def test_version_comes_from_version_file():
    assert get_version() == VERSION_FILE.read_text(encoding="utf-8").strip()
    assert get_version() == "1.0.0-rc.1"


def test_commit_from_env_is_sanitized(monkeypatch):
    monkeypatch.setenv("SIGOS_COMMIT", "ABCDEF0123456789abcdef0123456789abcdef01")
    assert get_commit() == "abcdef012345"


def test_commit_rejects_non_hex(monkeypatch):
    monkeypatch.setenv("SIGOS_COMMIT", "pwd=secret; rm -rf")
    monkeypatch.setattr(version_mod, "_commit_from_git", lambda: None)
    assert get_commit() is None


def test_health_keeps_legacy_contract(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "UP"
    assert body["checks"] == {"application": "UP", "database": "UP"}


def test_health_exposes_version_environment_latency(client):
    body = client.get("/api/v1/health").get_json()
    assert body["version"] == "1.0.0-rc.1"
    assert body["environment"] == "testing"
    assert "commit" in body
    assert isinstance(body["latency_ms"]["database"], (int, float))
    assert body["latency_ms"]["database"] >= 0


def test_health_db_down_returns_503_with_contract(client, app, monkeypatch):
    from app.extensions import db

    def boom(*a, **k):
        raise OperationalError("SELECT 1", {}, Exception("server=prod;pwd=x"))

    monkeypatch.setattr(db.session, "execute", boom)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["status"] == "DOWN"
    assert body["checks"] == {"application": "UP", "database": "DOWN"}
    assert "pwd" not in resp.get_data(as_text=True)


def test_live_ok_without_database(client, app, monkeypatch):
    from app.extensions import db

    def boom(*a, **k):
        raise AssertionError("live no debe consultar la base de datos")

    monkeypatch.setattr(db.session, "execute", boom)
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "UP"
    assert body["version"] == "1.0.0-rc.1"
    assert "checks" not in body


def test_live_requires_no_auth_and_is_not_cached(client):
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert "no-store" in resp.headers["Cache-Control"]


@pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/health/live"])
def test_no_secrets_in_health(client, app, path):
    text = client.get(path).get_data(as_text=True)
    payload = json.loads(text)
    assert set(payload) <= {"status", "checks", "latency_ms", "version", "environment", "commit"}
    forbidden = [app.config["JWT_SECRET_KEY"], app.config["SQLALCHEMY_DATABASE_URI"]]
    for value in forbidden:
        assert value not in text
    assert not re.search(r"(?i)password|pwd|secret|token|db_url|uid=", text)


def test_check_health_unit_without_app_context():
    class Session:
        def execute(self, statement):
            return None

        def rollback(self):
            pass

    body, status = health_service.check_health(Session())
    assert status == 200
    assert body["checks"]["database"] == "UP"
    assert body["environment"] is None
