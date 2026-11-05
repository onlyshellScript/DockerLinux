from sqlalchemy import text


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
