"""Prepara la base de datos antes de arrancar la API en el contenedor.

Modo aprovisionamiento (DB_ADMIN_URL o MSSQL_SA_PASSWORD definido, servicio `migrate`):
  1. Espera a SQL Server conectando con la cuenta administradora.
  2. Crea la base de datos de DB_URL si no existe.
  3. Crea (idempotente) el login/usuario migrador (DB_MIGRATOR_USER) con db_ddladmin,
     db_datareader y db_datawriter, y el de aplicación (DB_APP_USER) solo con
     db_datareader, db_datawriter y EXECUTE (se le retira db_ddladmin si lo tenía).
  4. Aplica las migraciones de Alembic (upgrade head) con el usuario migrador.

La URL de aplicación sale de DB_URL o se arma con DB_HOST/DB_NAME/DB_APP_USER/DB_APP_PASSWORD
(contraseñas codificadas, admiten @ y :). La administradora sale de DB_ADMIN_URL o de MSSQL_SA_PASSWORD.

Modo aplicación (sin DB_ADMIN_URL, servicios api/worker):
  Solo espera a que la base de DB_URL acepte conexiones del usuario de app y,
  si RUN_MIGRATIONS=true, migra.
"""
import os
import re
import sys
import time

import pyodbc
from sqlalchemy.engine import make_url

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import build_mssql_url, database_url, env_secret, env_str  # noqa: E402

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def _odbc_conn_str(url, database="master"):
    driver = url.query.get("driver", "ODBC Driver 18 for SQL Server")
    trust = url.query.get("TrustServerCertificate", "yes")
    host = url.host or "localhost"
    port = url.port or 1433
    return (
        f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};"
        f"UID={url.username};PWD={{{url.password.replace('}', '}}')}}};TrustServerCertificate={trust}"
    )


def _check_ident(value, what):
    if not value or not _IDENT.match(value):
        sys.exit(f"[prepare_db] {what} inválido: {value!r} (solo letras, números y _).")
    return value


def _connect(url, database, retries, delay):
    for attempt in range(1, retries + 1):
        try:
            return pyodbc.connect(_odbc_conn_str(url, database), autocommit=True, timeout=5)
        except pyodbc.Error as exc:
            print(f"[prepare_db] SQL Server no disponible ({attempt}/{retries}): {exc.args[0]}")
            time.sleep(delay)
    sys.exit("[prepare_db] No se pudo conectar a SQL Server.")


def _sql_str(value):
    return value.replace("'", "''")


def _ensure_login(conn, user, password, dbname):
    """CREATE LOGIN o ALTER LOGIN (contraseña). Aborta si el login existente es sysadmin."""
    row = conn.execute(
        "SELECT CASE WHEN SUSER_ID(?) IS NULL THEN 0 ELSE 1 END, ISNULL(IS_SRVROLEMEMBER('sysadmin', ?), 0)",
        user, user,
    ).fetchone()
    exists, is_sysadmin = int(row[0]), int(row[1])
    pwd = _sql_str(password)
    if not exists:
        conn.execute(
            f"CREATE LOGIN [{user}] WITH PASSWORD = N'{pwd}', CHECK_POLICY = ON, DEFAULT_DATABASE = [{dbname}];"
        )
        return
    if is_sysadmin:
        sys.exit(f"[prepare_db] El login '{user}' es miembro de sysadmin: se aborta (no se usa como cuenta de servicio).")
    conn.execute(f"ALTER LOGIN [{user}] WITH PASSWORD = N'{pwd}';")


def _ensure_user(conn, dbname, user, roles, drop_roles=(), grant_execute=False):
    conn.execute(f"USE [{dbname}]; IF USER_ID(N'{user}') IS NULL CREATE USER [{user}] FOR LOGIN [{user}];")
    for role in roles:
        conn.execute(
            f"USE [{dbname}]; IF IS_ROLEMEMBER(N'{role}', N'{user}') = 0 ALTER ROLE [{role}] ADD MEMBER [{user}];"
        )
    for role in drop_roles:
        conn.execute(
            f"USE [{dbname}]; IF IS_ROLEMEMBER(N'{role}', N'{user}') = 1 ALTER ROLE [{role}] DROP MEMBER [{user}];"
        )
    if grant_execute:
        conn.execute(f"USE [{dbname}]; GRANT EXECUTE TO [{user}];")


def provision(admin_url, app_url, migrator_url, retries, delay):
    """Crea base, login/usuario migrador (DDL) y login/usuario de aplicación (solo DML). Idempotente."""
    name = _check_ident(app_url.database, "Nombre de base")
    user = _check_ident(app_url.username, "Usuario de aplicación")
    mig = _check_ident(migrator_url.username, "Usuario migrador")
    admin_name = (admin_url.username or "").lower()
    for who in (user, mig):
        if who.lower() in ("sa", admin_name):
            sys.exit("[prepare_db] Los usuarios de aplicación y migrador deben ser distintos del administrador.")
    if user.lower() == mig.lower():
        sys.exit("[prepare_db] DB_APP_USER y DB_MIGRATOR_USER deben ser distintos.")
    if not app_url.password or not migrator_url.password:
        sys.exit("[prepare_db] Faltan contraseñas de aplicación o de migrador.")

    conn = _connect(admin_url, "master", retries, delay)
    try:
        conn.execute(f"IF DB_ID(N'{name}') IS NULL CREATE DATABASE [{name}]")
        print(f"[prepare_db] Base '{name}' lista.")
        _ensure_login(conn, mig, migrator_url.password, name)
        _ensure_user(conn, name, mig, ("db_ddladmin", "db_datareader", "db_datawriter"))
        print(f"[prepare_db] Login/usuario migrador '{mig}' listo (db_ddladmin, db_datareader, db_datawriter).")
        _ensure_login(conn, user, app_url.password, name)
        _ensure_user(conn, name, user, ("db_datareader", "db_datawriter"),
                     drop_roles=("db_ddladmin", "db_owner"), grant_execute=True)
        print(f"[prepare_db] Login/usuario de aplicación '{user}' listo (db_datareader, db_datawriter, EXECUTE).")
    finally:
        conn.close()


def wait_for_app_db(app_url, retries, delay):
    _check_ident(app_url.database, "Nombre de base")
    conn = _connect(app_url, app_url.database, retries, delay)
    try:
        who = conn.execute("SELECT SUSER_NAME()").fetchone()[0]
        print(f"[prepare_db] Conectado a '{app_url.database}' como '{who}'.")
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


def _admin_url():
    raw = os.environ.get("DB_ADMIN_URL")
    if raw:
        return make_url(raw)
    password = env_secret("MSSQL_SA_PASSWORD")
    if not password:
        return None
    return make_url(build_mssql_url(env_str("DB_ADMIN_USER", "sa"), password, "master"))


def _migrator_url(app_url):
    raw = env_secret("DB_MIGRATOR_URL")
    if raw:
        return make_url(raw)
    password = env_secret("DB_MIGRATOR_PASSWORD")
    if not password:
        sys.exit("[prepare_db] Falta DB_MIGRATOR_PASSWORD (obligatorio en el servicio migrate).")
    return make_url(build_mssql_url(env_str("DB_MIGRATOR_USER", "sigos_migrator"), password, app_url.database,
                                    host=app_url.host, port=app_url.port))


if __name__ == "__main__":
    db_url = database_url()
    if not db_url:
        sys.exit("[prepare_db] Falta DB_URL (o DB_HOST + DB_APP_PASSWORD).")
    url = make_url(db_url)
    retries = int(os.getenv("DB_WAIT_RETRIES", "30"))
    delay = float(os.getenv("DB_WAIT_DELAY", "2"))
    run = os.getenv("RUN_MIGRATIONS", "true").lower() == "true"

    if not url.drivername.startswith("mssql"):
        print(f"[prepare_db] Motor {url.drivername}: se omite la preparación.")
    else:
        admin = _admin_url()
        if admin:
            migrator = _migrator_url(url)
            provision(admin, url, migrator, retries, delay)
            wait_for_app_db(migrator, retries, delay)
            if run:
                # Alembic corre con el migrador; api/worker nunca reciben credenciales DDL.
                os.environ["DB_URL"] = migrator.render_as_string(hide_password=False)
                run_migrations()
                run = False
        wait_for_app_db(url, retries, delay)
    if run:
        run_migrations()
