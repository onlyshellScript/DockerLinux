import os
from datetime import timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass


# Configuración base de la aplicación: URI de base de datos, clave JWT y parámetros de seguridad. Lee valores desde variables de entorno.
class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DB_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    LOGIN_RATE_LIMIT_MAX = 5
    LOGIN_RATE_LIMIT_WINDOW = 300

    # Los tecnicos deben tener firma de perfil registrada para adjuntar evidencias (se copia en cada evidencia).
    EVIDENCE_REQUIRE_TECH_SIGNATURE = os.getenv("EVIDENCE_REQUIRE_TECH_SIGNATURE", "true").strip().lower() not in ("0", "false", "no")

# Configuración para pruebas automatizadas: BD SQLite en memoria, clave JWT fija y tokens de corta duración.
class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    JWT_SECRET_KEY = "test-secret"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
