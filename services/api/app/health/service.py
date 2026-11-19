from sqlalchemy import text


# Ejecuta SELECT 1 en la sesión de BD para verificar conectividad; devuelve estado UP con 200 si responde, o DOWN con 503 y rollback si falla. Efecto secundario: consulta la base de datos.
def check_health(session):
    try:
        session.execute(text("SELECT 1"))
        return {
            "status": "UP",
            "checks": {"application": "UP", "database": "UP"},
        }, 200
    except Exception:
        session.rollback()
        return {
            "status": "DOWN",
            "checks": {"application": "UP", "database": "DOWN"},
        }, 503
