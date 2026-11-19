"""Configuracion unificada de SIGOS (Fase 2, O5).

Jerarquia:
    BaseConfig
      +-- DevelopmentConfig   (SIGOS_ENV=development, predeterminado)
      +-- ProductionConfig    (SIGOS_ENV=production)
      +-- TestingConfig       (SIGOS_ENV=testing)

Los valores que dependen del entorno se leen *en el momento de construir la
aplicacion* (propiedades de instancia), no al importar el modulo. Asi un
cambio de variables de entorno antes de ``create_app`` se respeta y las
subclases pueden fijar valores con un atributo de clase normal.

Alias de compatibilidad: ``Config`` (= DevelopmentConfig), ``TestConfig``
(= TestingConfig) y ``app.config_prod.ProductionConfig``.
"""
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
    # SIGOS_ENV_FILE: archivo de entorno fuera del codigo (p. ej. servicio Windows en
    # C:\ProgramData\SIGOS\config\sigos.env). Se carga primero; load_dotenv no pisa variables ya definidas.
    if os.environ.get("SIGOS_ENV_FILE"):
        load_dotenv(os.environ["SIGOS_ENV_FILE"])
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

# Raiz del servicio API (services/api). Base para rutas relativas, independiente del directorio de trabajo.
API_ROOT = Path(__file__).resolve().parent.parent

_FALSE = ("0", "false", "no", "off")


def env_str(name, default=None):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def env_bool(name, default):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() not in _FALSE


def env_int(name, default):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value.strip())
    except ValueError as exc:
        raise RuntimeError(f"La variable de entorno {name} debe ser un entero") from exc


def env_secret(name, default=None):
    """Lee NAME o, si no existe, el contenido del archivo NAME_FILE (docker secrets)."""
    value = env_str(name)
    if value is not None:
        return value
    path = env_str(f"{name}_FILE")
    if path:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip() or default
    return default


def build_mssql_url(user, password, database, host=None, port=None):
    """URL SQLAlchemy de SQL Server con usuario y contrasena codificados (admite @ : / ? # %)."""
    host = host or env_str("DB_HOST", "localhost")
    port = port or env_str("DB_PORT", "1433")
    driver = env_str("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    trust = env_str("DB_TRUST_SERVER_CERTIFICATE", "yes")
    return (
        f"mssql+pyodbc://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(database)}"
        f"?driver={quote_plus(driver)}&TrustServerCertificate={quote_plus(trust)}"
    )


def database_url(name="DB_URL", default=None):
    """DB_URL (o DB_URL_FILE) si viene; si no, se arma con DB_HOST, DB_NAME, DB_APP_USER y DB_APP_PASSWORD."""
    url = env_secret(name)
    if url:
        return url
    if env_str("DB_HOST"):
        user = env_str("DB_APP_USER", "sigos_app")
        password = env_secret("DB_APP_PASSWORD")
        if password:
            return build_mssql_url(user, password, env_str("DB_NAME", "sigos"))
    return default


def resolve_path(raw, default):
    """Devuelve una ruta absoluta; las relativas se resuelven contra API_ROOT."""
    path = Path(raw) if raw else Path(default)
    if not path.is_absolute():
        path = API_ROOT / path
    return str(path.resolve())


class _Env:
    """Descriptor: lee la variable de entorno al acceder desde una instancia."""

    def __init__(self, reader, name, default=None):
        self.reader, self.name, self.default = reader, name, default

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return self.reader(self.name, self.default)


class BaseConfig:
    ENV_NAME = "base"
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Base de datos y autenticacion ---
    SQLALCHEMY_DATABASE_URI = _Env(database_url, "DB_URL")
    JWT_SECRET_KEY = _Env(env_secret, "JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    LOGIN_RATE_LIMIT_MAX = _Env(env_int, "LOGIN_RATE_LIMIT_MAX", 5)
    LOGIN_RATE_LIMIT_WINDOW = _Env(env_int, "LOGIN_RATE_LIMIT_WINDOW", 300)

    # --- Evidencias y almacenamiento ---
    # Los tecnicos deben tener firma de perfil registrada para adjuntar evidencias (se copia en cada evidencia).
    EVIDENCE_REQUIRE_TECH_SIGNATURE = _Env(env_bool, "EVIDENCE_REQUIRE_TECH_SIGNATURE", True)
    EVIDENCE_MAX_FILE_SIZE = _Env(env_int, "EVIDENCE_MAX_FILE_SIZE", 10 * 1024 * 1024)
    EVIDENCE_ALLOWED_MIME_TYPES = _Env(env_str, "EVIDENCE_ALLOWED_MIME_TYPES")

    @property
    def UPLOAD_DIR(self):
        # EVIDENCE_UPLOAD_DIR conserva su prioridad historica sobre UPLOAD_DIR.
        raw = env_str("EVIDENCE_UPLOAD_DIR") or env_str("UPLOAD_DIR")
        return resolve_path(raw, "uploads")

    # --- SMTP ---
    SMTP_HOST = _Env(env_str, "SMTP_HOST")
    SMTP_PORT = _Env(env_int, "SMTP_PORT", 587)
    SMTP_USER = _Env(env_str, "SMTP_USER")
    SMTP_PASS = _Env(env_str, "SMTP_PASS")

    @property
    def SMTP_FROM(self):
        return env_str("SMTP_FROM") or env_str("SMTP_USER")

    # --- WhatsApp ---
    WHATSAPP_API_URL = _Env(env_str, "WHATSAPP_API_URL")
    WHATSAPP_API_TOKEN = _Env(env_str, "WHATSAPP_API_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID = _Env(env_str, "WHATSAPP_PHONE_NUMBER_ID")

    # --- Logging ---
    LOG_LEVEL = _Env(env_str, "LOG_LEVEL", "INFO")
    LOG_FORMAT = _Env(env_str, "LOG_FORMAT", "text")


class DevelopmentConfig(BaseConfig):
    ENV_NAME = "development"


class ProductionConfig(BaseConfig):
    ENV_NAME = "production"
    LOG_FORMAT = _Env(env_str, "LOG_FORMAT", "json")


class TestingConfig(BaseConfig):
    """Aislada: nunca hereda credenciales ni servicios externos del entorno."""

    ENV_NAME = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "test-secret"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    LOGIN_RATE_LIMIT_MAX = 5
    LOGIN_RATE_LIMIT_WINDOW = 300
    SMTP_HOST = None
    SMTP_USER = None
    SMTP_PASS = None
    SMTP_FROM = None
    WHATSAPP_API_URL = None
    WHATSAPP_API_TOKEN = None
    WHATSAPP_PHONE_NUMBER_ID = None
    LOG_FORMAT = "text"


CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config_class(name=None):
    """Clase de configuracion segun ``name`` o SIGOS_ENV (predeterminado: development)."""
    key = (name or env_str("SIGOS_ENV") or "development").lower()
    aliases = {"dev": "development", "prod": "production", "test": "testing"}
    key = aliases.get(key, key)
    if key not in CONFIGS:
        raise RuntimeError(f"SIGOS_ENV desconocido: {key!r} (use development, production o testing)")
    return CONFIGS[key]


# Alias de compatibilidad con imports existentes.
Config = DevelopmentConfig
TestConfig = TestingConfig
