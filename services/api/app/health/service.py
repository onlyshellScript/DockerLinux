import time

from flask import current_app, has_app_context
from sqlalchemy import text

from app.version import get_commit, get_version


# _metadata: version, entorno y commit. Nunca incluye URL de BD, credenciales ni variables de entorno.
def _metadata():
    env = current_app.config.get("ENV_NAME", "development") if has_app_context() else None
    return {"version": get_version(), "environment": env, "commit": get_commit()}


# Ejecuta SELECT 1 en la sesión de BD para verificar conectividad; devuelve estado UP con 200 si responde, o DOWN con 503 y rollback si falla.
# Conserva "status" y "checks" (contrato de Desktop y Flutter) y agrega metadatos y latencia de BD en milisegundos.
def check_health(session):
    started = time.perf_counter()
    try:
        session.execute(text("SELECT 1"))
        db_status, status, code = "UP", "UP", 200
    except Exception:
        session.rollback()
        db_status, status, code = "DOWN", "DOWN", 503
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    body = {
        "status": status,
        "checks": {"application": "UP", "database": db_status},
        "latency_ms": {"database": latency_ms},
    }
    body.update(_metadata())
    return body, code


# check_liveness: solo confirma que el proceso responde; no toca la base de datos.
def check_liveness():
    body = {"status": "UP"}
    body.update(_metadata())
    return body, 200
