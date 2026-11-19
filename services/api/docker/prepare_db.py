"""Prepara la base de datos antes de arrancar la API en el contenedor.

1. Espera a que SQL Server acepte conexiones (reintentos).
2. Crea la base de datos indicada en DB_URL si no existe.
3. Aplica las migraciones de Alembic (upgrade head).
"""
import os
import sys
import time

import pyodbc
from sqlalchemy.engine import make_url


def _odbc_conn_str(url, database="master"):
    driver = url.query.get("driver", "ODBC Driver 18 for SQL Server")
    trust = url.query.get("TrustServerCertificate", "yes")
    host = url.host or "localhost"
    port = url.port or 1433
    return (
        f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};"
        f"UID={url.username};PWD={url.password};TrustServerCertificate={trust}"
    )


def wait_and_create_database(db_url, retries, delay):
    url = make_url(db_url)
    if not url.drivername.startswith("mssql"):
        print(f"[prepare_db] Motor {url.drivername}: se omite la creación de la base.")
        return
    name = url.database
    if not name or not name.replace("_", "").isalnum():
        sys.exit(f"[prepare_db] Nombre de base inválido en DB_URL: {name!r}")

    for attempt in range(1, retries + 1):
        try:
            conn = pyodbc.connect(_odbc_conn_str(url), autocommit=True, timeout=5)
            break
        except pyodbc.Error as exc:
            print(f"[prepare_db] SQL Server no disponible ({attempt}/{retries}): {exc.args[0]}")
            time.sleep(delay)
    else:
        sys.exit("[prepare_db] No se pudo conectar a SQL Server.")

    try:
        conn.execute(f"IF DB_ID(N'{name}') IS NULL CREATE DATABASE [{name}]")
        print(f"[prepare_db] Base '{name}' lista.")
    finally:
        conn.close()


def run_migrations():
    from flask_migrate import upgrade

    from app import create_app
    from app.config import ProductionConfig

    app = create_app(ProductionConfig)
    with app.app_context():
        upgrade(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"))
    print("[prepare_db] Migraciones aplicadas.")


if __name__ == "__main__":
    db_url = os.environ.get("DB_URL")
    if not db_url:
        sys.exit("[prepare_db] Falta DB_URL.")
    wait_and_create_database(
        db_url,
        retries=int(os.getenv("DB_WAIT_RETRIES", "30")),
        delay=float(os.getenv("DB_WAIT_DELAY", "2")),
    )
    if os.getenv("RUN_MIGRATIONS", "true").lower() == "true":
        run_migrations()
