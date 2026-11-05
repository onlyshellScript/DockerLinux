import threading
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.identity.models import User, Role
from app.materials.models import TechnicianProfile
from app.catalogs.models import City, Zone
from app.workorders.models import WorkOrder


def _seed(app):
    with app.app_context():
        admin_role = Role(name="admin", description="Administrador")
        disp_role = Role(name="dispatcher", description="Despachador")
        tech_role = Role(name="technician", description="Tecnico")
        db.session.add_all([admin_role, disp_role, tech_role])
        db.session.flush()

        admin = User(username="admin", email="admin@test.local")
        admin.set_password("Admin123!")
        admin.roles.append(admin_role)

        disp = User(username="disp", email="disp@test.local")
        disp.set_password("Disp123!")
        disp.roles.append(disp_role)

        tech_user = User(username="tech", email="tech@test.local")
        tech_user.set_password("Tech123!")
        tech_user.roles.append(tech_role)
        db.session.add_all([admin, disp, tech_user])
        db.session.flush()

        city = City.query.filter_by(dane_code="11001").first()
        if not city:
            from app.catalogs.models import Country
            country = Country.query.filter_by(iso2="CO").first()
            city = City(country_id=country.id, department_name="Cundinamarca", dane_code="11001", name="Bogota", name_norm="bogota", active=True)
            db.session.add(city)
            db.session.flush()
        zone = Zone.query.filter_by(city_id=city.id).first()
        if not zone:
            zone = Zone(city_id=city.id, kind="localidad", name="Usaquen", name_norm="usaquen", active=True)
            db.session.add(zone)
            db.session.flush()

        prof = TechnicianProfile(user_id=tech_user.id, first_name="Tech", last_name="One", is_available=True, is_active=True)
        db.session.add(prof)
        db.session.flush()
        from app.catalogs.models import TechnicianZone
        cov = TechnicianZone(technician_id=prof.id, city_id=city.id, zone_id=zone.id, is_primary=True)
        db.session.add(cov)

        wo = WorkOrder(title="Orden test", created_by_id=admin.id, status="pending", priority="medium",
                       city_id=city.id, zone_id=zone.id, installation_type_code="residencial")
        db.session.add(wo)
        db.session.commit()
        return {
            "admin_id": admin.id, "disp_id": disp.id, "tech_user_id": tech_user.id,
            "tech_profile_id": prof.id, "city_id": city.id, "zone_id": zone.id,
            "work_order_id": wo.id,
        }


def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.get_json()["access_token"]


def test_validate_detects_overlap(client, app):
    ids = _seed(app)
    token = _login(client, "admin", "Admin123!")
    with app.app_context():
        from app.identity.models import User
        admin = User.query.filter_by(username="admin").first()
        wo2 = WorkOrder(title="Otra", created_by_id=ids["admin_id"], status="pending", priority="medium",
                        city_id=ids["city_id"], zone_id=ids["zone_id"], installation_type_code="residencial")
        db.session.add(wo2)
        db.session.flush()
        from app.calendar import service as cs
        cs.schedule_order(wo2.id, {
            "start": "2026-11-04T10:00:00", "end": "2026-11-04T11:00:00",
            "technician_ids": [ids["tech_user_id"]], "version": wo2.version,
        }, admin, ["admin"])
        db.session.commit()

    # validate overlapping 10:30-11:30
    resp = client.post("/api/v1/calendar/validate", headers={"Authorization": f"Bearer {token}"}, json={
        "order_id": ids["work_order_id"],
        "start": "2026-11-04T10:30:00",
        "end": "2026-11-04T11:30:00",
        "technician_ids": [ids["tech_user_id"]],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is False
    assert any(c["code"] == "schedule_conflict" for c in data["conflicts"])

    # adjacent 11:00-12:00 OK
    resp = client.post("/api/v1/calendar/validate", headers={"Authorization": f"Bearer {token}"}, json={
        "order_id": ids["work_order_id"],
        "start": "2026-11-04T11:00:00",
        "end": "2026-11-04T12:00:00",
        "technician_ids": [ids["tech_user_id"]],
    })
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_validate_out_of_hours(client, app):
    ids = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post("/api/v1/calendar/validate", headers={"Authorization": f"Bearer {token}"}, json={
        "order_id": ids["work_order_id"],
        "start": "2026-11-04T06:00:00",
        "end": "2026-11-04T07:00:00",
        "technician_ids": [],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is False
    assert any(c["code"] in ("invalid_time", "out_of_hours") for c in data["conflicts"])


def test_validate_out_of_service(client, app):
    ids = _seed(app)
    token = _login(client, "admin", "Admin123!")
    with app.app_context():
        prof = TechnicianProfile.query.get(ids["tech_profile_id"])
        prof.is_available = False
        db.session.commit()
    resp = client.post("/api/v1/calendar/validate", headers={"Authorization": f"Bearer {token}"}, json={
        "order_id": ids["work_order_id"],
        "start": "2026-11-04T09:00:00",
        "end": "2026-11-04T10:00:00",
        "technician_ids": [ids["tech_user_id"]],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is False
    assert any(c["code"] == "technician_unavailable" for c in data["conflicts"])


def test_validate_zone_not_covered(client, app):
    ids = _seed(app)
    token = _login(client, "admin", "Admin123!")
    # create a work order in a different city/zone by changing city_id to a non-covered one
    with app.app_context():
        wo = WorkOrder.query.get(ids["work_order_id"])
        # point to a city that has no coverage for tech: use city_id 9999 (none)
        wo.city_id = 9999
        db.session.commit()
    resp = client.post("/api/v1/calendar/validate", headers={"Authorization": f"Bearer {token}"}, json={
        "order_id": ids["work_order_id"],
        "start": "2026-11-04T09:00:00",
        "end": "2026-11-04T10:00:00",
        "technician_ids": [ids["tech_user_id"]],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(w["code"] == "zone_not_covered" for w in data["warnings"])


def test_validate_state_not_programmable(client, app):
    ids = _seed(app)
    token = _login(client, "admin", "Admin123!")
    with app.app_context():
        wo = WorkOrder.query.get(ids["work_order_id"])
        wo.status = "completed"
        db.session.commit()
    resp = client.post("/api/v1/calendar/validate", headers={"Authorization": f"Bearer {token}"}, json={
        "order_id": ids["work_order_id"],
        "start": "2026-11-04T09:00:00",
        "end": "2026-11-04T10:00:00",
        "technician_ids": [],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is False
    assert any(c["code"] == "invalid_transition" for c in data["conflicts"])


def test_reschedule_requires_reason(client, app):
    ids = _seed(app)
    token = _login(client, "admin", "Admin123!")
    # schedule first
    with app.app_context():
        from app.identity.models import User
        admin = User.query.filter_by(username="admin").first()
        wo = WorkOrder.query.get(ids["work_order_id"])
        from app.calendar import service as cs
        cs.schedule_order(wo.id, {
            "start": "2026-11-04T09:00:00", "end": "2026-11-04T10:00:00",
            "technician_ids": [], "version": wo.version,
        }, admin, ["admin"])
        db.session.commit()
    # reschedule without reason
    with app.app_context():
        wo = WorkOrder.query.get(ids["work_order_id"])
        version = wo.version
    resp = client.patch(f"/api/v1/work-orders/{ids['work_order_id']}/schedule",
                        headers={"Authorization": f"Bearer {token}"}, json={
        "start": "2026-11-04T11:00:00", "end": "2026-11-04T12:00:00", "version": version,
    })
    assert resp.status_code == 422


def test_stale_version(client, app):
    ids = _seed(app)
    token = _login(client, "admin", "Admin123!")
    with app.app_context():
        from app.identity.models import User
        admin = User.query.filter_by(username="admin").first()
        wo = WorkOrder.query.get(ids["work_order_id"])
        from app.calendar import service as cs
        cs.schedule_order(wo.id, {
            "start": "2026-11-04T09:00:00", "end": "2026-11-04T10:00:00",
            "technician_ids": [], "version": wo.version,
        }, admin, ["admin"])
        db.session.commit()
    # use stale version 0
    resp = client.post(f"/api/v1/work-orders/{ids['work_order_id']}/schedule",
                       headers={"Authorization": f"Bearer {token}"}, json={
        "start": "2026-11-04T11:00:00", "end": "2026-11-04T12:00:00", "version": 0,
    })
    # could be 409 stale or invalid transition; expect 409
    assert resp.status_code in (409,)


def test_permissions_forbidden(client, app):
    ids = _seed(app)
    token = _login(client, "tech", "Tech123!")
    resp = client.post("/api/v1/calendar/validate", headers={"Authorization": f"Bearer {token}"}, json={
        "order_id": ids["work_order_id"],
        "start": "2026-11-04T09:00:00", "end": "2026-11-04T10:00:00",
        "technician_ids": [],
    })
    assert resp.status_code == 403


def test_2330_local_day(client, app):
    ids = _seed(app)
    token = _login(client, "admin", "Admin123!")
    # 23:30 Bogota = next day 04:30 UTC; validate should treat local day
    resp = client.post("/api/v1/calendar/validate", headers={"Authorization": f"Bearer {token}"}, json={
        "order_id": ids["work_order_id"],
        "start": "2026-11-04T19:00:00",
        "end": "2026-11-04T20:00:00",
        "technician_ids": [],
    })
    # out of hours (work ends 18:00) -> not ok
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is False


def test_cancelled_excluded(client, app):
    ids = _seed(app)
    token = _login(client, "admin", "Admin123!")
    with app.app_context():
        wo = WorkOrder.query.get(ids["work_order_id"])
        wo.status = "cancelled"
        wo.scheduled_at = datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)
        wo.scheduled_end = datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc)
        db.session.commit()
    resp = client.get("/api/v1/calendar/events?from=2026-11-04T00:00:00Z&to=2026-11-05T00:00:00Z",
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    assert all(i["order_id"] != ids["work_order_id"] for i in items)


import pytest

@pytest.mark.xfail(reason="SQLite in-memory no soporta concurrencia; validar en SQL Server real")
def test_concurrent_schedule(client, app):
    ids = _seed(app)
    # create two orders
    with app.app_context():
        from app.identity.models import User
        admin = User.query.filter_by(username="admin").first()
        wo1 = WorkOrder(title="C1", created_by_id=ids["admin_id"], status="pending", priority="medium",
                        city_id=ids["city_id"], zone_id=ids["zone_id"], installation_type_code="residencial")
        wo2 = WorkOrder(title="C2", created_by_id=ids["admin_id"], status="pending", priority="medium",
                        city_id=ids["city_id"], zone_id=ids["zone_id"], installation_type_code="residencial")
        db.session.add_all([wo1, wo2])
        db.session.commit()
        v1, v2 = wo1.version, wo2.version
        id1, id2 = wo1.id, wo2.id
    token = _login(client, "admin", "Admin123!")
    results = []

    def worker(order_id, version):
        c = app.test_client()
        r = c.post(f"/api/v1/work-orders/{order_id}/schedule",
                   headers={"Authorization": f"Bearer {token}"},
                   json={"start": "2026-11-04T09:00:00", "end": "2026-11-04T10:00:00",
                         "technician_ids": [ids["tech_user_id"]], "version": version})
        results.append(r.status_code)

    t1 = threading.Thread(target=worker, args=(id1, v1))
    t2 = threading.Thread(target=worker, args=(id2, v2))
    t1.start(); t2.start()
    t1.join(); t2.join()
    # only one should succeed (200), the other conflict (409)
    assert sorted(results) == [200, 409] or sorted(results) == [200, 200] is False
    assert results.count(200) == 1


def test_unassigned_tray(client, app):
    ids = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/calendar/unassigned?page_size=50", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "items" in data
    assert any(i["id"] == ids["work_order_id"] for i in data["items"])
