# Fase 2 / O5: configuracion unificada (BaseConfig + entornos, SIGOS_ENV, alias y rutas absolutas).
import os
from pathlib import Path

import pytest

from app import create_app
from app.config import (
    API_ROOT, BaseConfig, Config, DevelopmentConfig, ProductionConfig,
    TestConfig, TestingConfig, get_config_class,
)

SECRET_VARS = ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "WHATSAPP_API_URL",
               "WHATSAPP_API_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET_KEY", "o5-secret")
    for name in ("SIGOS_ENV", "UPLOAD_DIR", "EVIDENCE_UPLOAD_DIR", "LOG_FORMAT"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_compat_aliases():
    from app.config_prod import ProductionConfig as Prod
    assert Prod is ProductionConfig
    assert Config is DevelopmentConfig
    assert TestConfig is TestingConfig
    for cls in (DevelopmentConfig, ProductionConfig, TestingConfig):
        assert issubclass(cls, BaseConfig)


@pytest.mark.parametrize("value,expected", [
    (None, DevelopmentConfig), ("development", DevelopmentConfig), ("production", ProductionConfig),
    ("PROD", ProductionConfig), ("testing", TestingConfig), ("test", TestingConfig),
])
def test_sigos_env_selection(env, value, expected):
    if value:
        env.setenv("SIGOS_ENV", value)
    assert get_config_class() is expected


def test_sigos_env_unknown_fails(env):
    env.setenv("SIGOS_ENV", "staging-x")
    with pytest.raises(RuntimeError):
        get_config_class()


@pytest.mark.parametrize("name", ["development", "production", "testing"])
def test_app_starts_in_each_environment(env, name):
    env.setenv("SIGOS_ENV", name)
    app = create_app()
    assert app.config["ENV_NAME"] == name
    assert app.config["TESTING"] is (name == "testing")
    assert "health" in app.blueprints


def test_production_requires_secrets(env):
    env.delenv("JWT_SECRET_KEY")
    with pytest.raises(RuntimeError):
        create_app(ProductionConfig)


def test_env_read_at_build_time_not_import_time(env):
    env.setenv("LOGIN_RATE_LIMIT_MAX", "9")
    app = create_app(DevelopmentConfig)
    assert app.config["LOGIN_RATE_LIMIT_MAX"] == 9
    assert app.config["JWT_SECRET_KEY"] == "o5-secret"


def test_testing_does_not_inherit_secrets(env):
    env.setenv("DB_URL", "mssql+pyodbc://prod-host/SIGOS")
    env.setenv("JWT_SECRET_KEY", "prod-secret")
    for name in SECRET_VARS:
        env.setenv(name, "leak")
    app = create_app(TestingConfig)
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
    assert app.config["JWT_SECRET_KEY"] == "test-secret"
    for name in SECRET_VARS:
        assert app.config[name] is None, name


def test_upload_dir_default_is_absolute_under_api_root(env):
    cfg = DevelopmentConfig()
    assert Path(cfg.UPLOAD_DIR).is_absolute()
    assert Path(cfg.UPLOAD_DIR) == (API_ROOT / "uploads").resolve()


def test_upload_dir_relative_and_absolute(env, tmp_path):
    env.setenv("UPLOAD_DIR", "data/up")
    assert Path(DevelopmentConfig().UPLOAD_DIR) == (API_ROOT / "data/up").resolve()
    env.setenv("UPLOAD_DIR", str(tmp_path))
    assert Path(DevelopmentConfig().UPLOAD_DIR) == tmp_path.resolve()
    env.setenv("EVIDENCE_UPLOAD_DIR", str(tmp_path / "ev"))
    assert Path(DevelopmentConfig().UPLOAD_DIR) == (tmp_path / "ev").resolve()


def test_storage_uses_configured_upload_dir(env, tmp_path):
    from app.evidence.storage import LocalStorage
    env.setenv("UPLOAD_DIR", str(tmp_path / "store"))
    app = create_app(DevelopmentConfig)
    with app.app_context():
        storage = LocalStorage()
    assert storage.base_dir == (tmp_path / "store").resolve()
    assert (tmp_path / "store" / "originals").is_dir()


def test_log_format_defaults(env):
    assert DevelopmentConfig().LOG_FORMAT == "text"
    assert ProductionConfig().LOG_FORMAT == "json"
    env.setenv("LOG_FORMAT", "text")
    assert ProductionConfig().LOG_FORMAT == "text"


def test_invalid_int_env_is_explicit(env):
    env.setenv("SMTP_PORT", "abc")
    with pytest.raises(RuntimeError):
        DevelopmentConfig().SMTP_PORT


def test_senders_use_central_config_in_testing(env):
    from app.notifications.senders import send_email, send_whatsapp
    env.setenv("SMTP_HOST", "smtp.real.example")
    env.setenv("WHATSAPP_API_URL", "https://real.example")
    app = create_app(TestingConfig)
    with app.app_context():
        assert send_email("a@b.c", "s", "m") == (False, "SMTP_HOST not configured")
        assert send_whatsapp("+500", "m") == (False, "WHATSAPP_API_URL not configured")
