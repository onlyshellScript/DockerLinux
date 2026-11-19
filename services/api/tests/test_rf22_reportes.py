# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.

from app.extensions import db
from app.identity.models import User, Role
from app.workorders.models import WorkOrder

# Inserta datos iniciales en la base; recibe app; interactua con la base de datos; devuelve el valor correspondiente.

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
        tech = User(username="tech", email="tech@test.local")
        tech.set_password("Tech123!")
        tech.roles.append(tech_role)
        db.session.add_all([admin, disp, tech])
        db.session.flush()
        o1 = WorkOrder(title="O1", created_by_id=admin.id, status="pending", priority="medium", zone="Z1", assigned_to_id=tech.id)
        o2 = WorkOrder(title="O2", created_by_id=admin.id, status="completed", priority="medium", zone="Z2", assigned_to_id=tech.id)
        o3 = WorkOrder(title="O3", created_by_id=admin.id, status="cancelled", priority="medium", zone="Z1")
        db.session.add_all([o1, o2, o3])
        db.session.commit()
        return admin.id, disp.id, tech.id


# _login: realiza login y devuelve el access_token; entradas client, username, password; salida str; efecto secundario autentica.
def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]

# test_rf22_401_sin_sesion: valida el escenario rf22 401 sin sesion preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_401_sin_sesion(client):
    resp = client.get("/api/v1/reportes/ordenes")
    assert resp.status_code == 401

# test_rf22_403_tecnico: valida el escenario rf22 403 tecnico preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_403_tecnico(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "tech", "Tech123!")
    resp = client.get("/api/v1/reportes/ordenes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403

# test_rf22_admin_ok: valida el escenario rf22 admin ok preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_admin_ok(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/reportes/ordenes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "resumen" in data and "items" in data and "filtros" in data

# test_rf22_filtro_estado: valida el escenario rf22 filtro estado preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_filtro_estado(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/reportes/ordenes?estado=completed", headers={"Authorization": f"Bearer {token}"})
    data = resp.get_json()
    assert data["total"] == 1
    assert all(i["status"] == "completed" for i in data["items"])

# test_rf22_filtro_tecnico: valida el escenario rf22 filtro tecnico preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_filtro_tecnico(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get(f"/api/v1/reportes/ordenes?tecnico_id={tech_id}", headers={"Authorization": f"Bearer {token}"})
    data = resp.get_json()
    assert data["total"] == 2

# test_rf22_filtro_zona: valida el escenario rf22 filtro zona preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_filtro_zona(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/reportes/ordenes?zona=Z1", headers={"Authorization": f"Bearer {token}"})
    data = resp.get_json()
    assert data["total"] == 2

# test_rf22_filtros_combinados: valida el escenario rf22 filtros combinados preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_filtros_combinados(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/reportes/ordenes?estado=pending&zona=Z1", headers={"Authorization": f"Bearer {token}"})
    data = resp.get_json()
    assert data["total"] == 1

# test_rf22_paginacion: valida el escenario rf22 paginacion preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_paginacion(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/reportes/ordenes?por_pagina=1&pagina=2", headers={"Authorization": f"Bearer {token}"})
    data = resp.get_json()
    assert data["page"] == 2
    assert len(data["items"]) == 1

# test_rf22_validacion_estado: valida el escenario rf22 validacion estado preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_validacion_estado(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/reportes/ordenes?estado=foo", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400

# test_rf22_validacion_fechas: valida el escenario rf22 validacion fechas preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_validacion_fechas(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/reportes/ordenes?desde=2026-01-01&hasta=2025-01-01", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400
    resp = client.get("/api/v1/reportes/ordenes?desde=not-a-date", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400

# test_rf22_campo_fecha: valida el escenario rf22 campo fecha preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_campo_fecha(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/reportes/ordenes?campo_fecha=scheduled_at", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    resp = client.get("/api/v1/reportes/ordenes?campo_fecha=foo", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400

# test_rf22_dispatcher_ok: valida el escenario rf22 dispatcher ok preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf22_dispatcher_ok(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "disp", "Disp123!")
    resp = client.get("/api/v1/reportes/ordenes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

# test_reportes_export_xlsx_openpyxl: valida el escenario reportes export xlsx openpyxl preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_reportes_export_xlsx_openpyxl(client, app):
    from openpyxl import load_workbook
    import io
    admin_id, disp_id, tech_id = _seed_admin_dispatcher_tech(app) if False else (None, None, None)
    # reuse seed from test file? Use simple admin seed
    from app.identity.models import User, Role
    from app.extensions import db
    with app.app_context():
        if not Role.query.filter_by(name="admin").first():
            db.session.add(Role(name="admin", description="Administrador"))
        if not Role.query.filter_by(name="dispatcher").first():
            db.session.add(Role(name="dispatcher", description="Despachador"))
        db.session.flush()
        if not User.query.filter_by(username="admin").first():
            u = User(username="admin", email="admin@test.local")
            u.set_password("Admin123!")
            u.roles.append(Role.query.filter_by(name="admin").first())
            db.session.add(u)
        db.session.commit()
    token = _login(client, "admin", "Admin123!") if False else None
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
    token = resp.get_json()["access_token"]
    client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json={"title": "Orden reporte"})
    resp = client.get("/api/v1/reportes/ordenes?formato=xlsx", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.data))
    assert wb.active is not None

# test_reportes_export_pdf_valid: valida el escenario reportes export pdf valid preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_reportes_export_pdf_valid(client, app):
    from app.identity.models import User, Role
    from app.extensions import db
    with app.app_context():
        if not Role.query.filter_by(name="admin").first():
            db.session.add(Role(name="admin", description="Administrador"))
        db.session.flush()
        if not User.query.filter_by(username="admin").first():
            u = User(username="admin", email="admin@test.local")
            u.set_password("Admin123!")
            u.roles.append(Role.query.filter_by(name="admin").first())
            db.session.add(u)
        db.session.commit()
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
    token = resp.get_json()["access_token"]
    resp = client.get("/api/v1/reportes/ordenes?formato=pdf", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.data.startswith(b"%PDF")

# test_dashboard_kpis_present: valida el escenario dashboard kpis present preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_dashboard_kpis_present(client, app):
    from app.identity.models import User, Role
    from app.extensions import db
    with app.app_context():
        if not Role.query.filter_by(name="admin").first():
            db.session.add(Role(name="admin", description="Administrador"))
        db.session.flush()
        if not User.query.filter_by(username="admin").first():
            u = User(username="admin", email="admin@test.local")
            u.set_password("Admin123!")
            u.roles.append(Role.query.filter_by(name="admin").first())
            db.session.add(u)
        db.session.commit()
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
    token = resp.get_json()["access_token"]
    resp = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "kpis" in data
    assert len(data["kpis"]) >= 6
