# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.

import pytest

from app.extensions import db
from app.identity.models import User, Role
from app.materials.models import TechnicianProfile
from app.catalogs.models import City, Zone
from app.workorders.models import WorkOrder

# Inserta datos iniciales en la base; recibe app, active; interactua con la base de datos; devuelve el valor correspondiente.

def _seed(app, active=True):
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
        prof = TechnicianProfile(user_id=tech_user.id, first_name="Tech", last_name="One", is_available=True, is_active=active)
        db.session.add(prof)
        db.session.flush()
        from app.catalogs.models import TechnicianZone
        cov = TechnicianZone(technician_id=prof.id, city_id=city.id, zone_id=zone.id, is_primary=True)
        db.session.add(cov)
        wo = WorkOrder(title="Orden test", created_by_id=admin.id, status="pending", priority="medium", city_id=city.id, zone_id=zone.id)
        db.session.add(wo)
        db.session.commit()
        return {"admin_id": admin.id, "tech_user_id": tech_user.id, "tech_profile_id": prof.id, "work_order_id": wo.id}


# _login: realiza login y devuelve el access_token; entradas client, username, password; salida str; efecto secundario autentica.
def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]

# test_rf09_rechaza_tecnico_inactivo: valida el escenario rf09 rechaza tecnico inactivo preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf09_rechaza_tecnico_inactivo(client, app):
    ids = _seed(app, active=False)
    token = _login(client, "disp", "Disp123!")
    resp = client.post(f"/api/v1/work-orders/{ids['work_order_id']}/assignments",
                       headers={"Authorization": f"Bearer {token}"},
                       json={"technician_id": ids["tech_user_id"], "scheduled_at": "2026-11-04T09:00:00"})
    assert resp.status_code == 422

# test_rf09_rechaza_sin_rol_tecnico: valida el escenario rf09 rechaza sin rol tecnico preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf09_rechaza_sin_rol_tecnico(client, app):
    ids = _seed(app)
    with app.app_context():
        from app.identity.models import User
        u = User(username="no", email="no@test.local")
        u.set_password("No123!")
        db.session.add(u)
        db.session.commit()
        uid = u.id
    token = _login(client, "disp", "Disp123!")
    resp = client.post(f"/api/v1/work-orders/{ids['work_order_id']}/assignments",
                       headers={"Authorization": f"Bearer {token}"},
                       json={"technician_id": uid, "scheduled_at": "2026-11-04T09:00:00"})
    assert resp.status_code in (400, 422, 409)

# test_rf09_rechaza_solape_horario: valida el escenario rf09 rechaza solape horario preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf09_rechaza_solape_horario(client, app):
    ids = _seed(app, active=True)
    token = _login(client, "disp", "Disp123!")
    with app.app_context():
        from app.identity.models import User
        from app.calendar import service as cs
        disp = User.query.filter_by(username="disp").first()
        wo = WorkOrder.query.get(ids["work_order_id"])
        cs.schedule_order(wo.id, {
            "start": "2026-11-04T09:00:00", "end": "2026-11-04T10:00:00",
            "technician_ids": [ids["tech_user_id"]], "version": wo.version,
        }, disp, ["dispatcher"])
        db.session.commit()
    with app.app_context():
        admin_id = User.query.filter_by(username="admin").first().id
        wo2 = WorkOrder(title="O2", created_by_id=admin_id, status="pending", priority="medium")
        db.session.add(wo2)
        db.session.commit()
        wo2_id = wo2.id
        version = wo2.version
    resp = client.post(f"/api/v1/work-orders/{wo2_id}/schedule",
                       headers={"Authorization": f"Bearer {token}"},
                       json={"start": "2026-11-04T09:30:00", "end": "2026-11-04T10:30:00",
                             "technician_ids": [ids["tech_user_id"]], "version": version})
    assert resp.status_code in (409, 422)
