# Pruebas de Configuracion > Operacion: validaciones de PATCH, control de version y simulacro de impacto.
from datetime import datetime, timezone

from app.extensions import db
from app.identity.models import Role, User
from app.workorders.models import WorkOrder


def _seed(app):
    with app.app_context():
        role = Role(name="admin", description="admin")
        db.session.add(role)
        u = User(username="admin", email="admin@test.local")
        u.set_password("Admin12345!")
        u.roles.append(role)
        db.session.add(u)
        db.session.commit()
        return u.id


def _h(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin12345!"})
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def test_operations_rejects_contradictory_values(client, app):
    _seed(app)
    h = _h(client)
    v = client.get("/api/v1/settings/operations", headers=h).get_json()["version"]
    assert client.patch("/api/v1/settings/operations", headers=h, json={"version": v, "work_start": "18:00", "work_end": "07:00"}).status_code == 422
    assert client.patch("/api/v1/settings/operations", headers=h, json={"version": v, "calendar_interval": 20}).status_code == 422
    assert client.patch("/api/v1/settings/operations", headers=h, json={"version": v, "work_days": []}).status_code == 422
    r = client.patch("/api/v1/settings/operations", headers=h, json={"version": v, "work_start": "08:00", "work_end": "17:00", "work_days": [1, 2, 3, 4, 5, 6]})
    assert r.status_code == 200
    data = client.get("/api/v1/settings/operations", headers=h).get_json()
    assert (data["work_start"], data["work_end"], data["work_days"]) == ("08:00", "17:00", [1, 2, 3, 4, 5, 6])
    # version anterior => conflicto
    assert client.patch("/api/v1/settings/operations", headers=h, json={"version": v, "travel_margin_minutes": 10}).status_code == 409


def test_operations_impact_counts_scheduled_orders(client, app):
    uid = _seed(app)
    with app.app_context():
        # Domingo 22/11/2026 10:00 hora Bogota (15:00 UTC): fuera de lunes-viernes
        db.session.add(WorkOrder(title="Visita domingo", created_by_id=uid, status="assigned", priority="medium",
                                 scheduled_at=datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc),
                                 scheduled_end=datetime(2026, 11, 22, 16, 0, tzinfo=timezone.utc)))
        # Lunes 23/11/2026 09:00 Bogota: dentro de horario
        db.session.add(WorkOrder(title="Visita lunes", created_by_id=uid, status="assigned", priority="medium",
                                 scheduled_at=datetime(2026, 11, 23, 14, 0, tzinfo=timezone.utc),
                                 scheduled_end=datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc)))
        db.session.commit()
    h = _h(client)
    r = client.post("/api/v1/settings/operations/impact", headers=h, json={"work_days": [1, 2, 3, 4, 5]})
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 1 and body["items"][0]["violations"] == ["día no laboral"]
    r = client.post("/api/v1/settings/operations/impact", headers=h, json={"work_days": [1, 2, 3, 4, 5, 6, 7], "work_start": "16:00"})
    assert r.get_json()["count"] == 2  # ambas empiezan antes de las 16:00 (hora local o UTC: SQLite guarda sin zona)
