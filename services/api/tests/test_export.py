# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.
from app.extensions import db
from app.identity.models import User, Role
from app.materials.models import MaterialCatalog

# Inserta datos iniciales en la base; recibe app; interactua con la base de datos; accede al sistema de archivos; devuelve el valor correspondiente.

def _seed(app):
    import os, sys
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if base not in sys.path:
        sys.path.insert(0, base)
    with app.app_context():
        admin_role = Role(name="admin", description="Administrador")
        disp_role = Role(name="dispatcher", description="Despachador")
        db.session.add_all([admin_role, disp_role])
        db.session.flush()
        admin = User(username="admin", email="admin@test.local")
        admin.set_password("Admin123!")
        admin.roles.append(admin_role)
        disp = User(username="disp", email="disp@test.local")
        disp.set_password("Disp123!")
        disp.roles.append(disp_role)
        db.session.add_all([admin, disp])
        db.session.commit()
        from seeds.load_catalog import load_into_app
        load_into_app(app, os.path.join(base, "seeds", "materiales_gas_natural.json"))
        ci = MaterialCatalog.query.first()
        from app.materials.models import Material
        m = Material(name=ci.name, code=ci.code, unit="pza", current_stock=5, min_stock=2, unit_price=1000, catalog_item_id=ci.id)
        db.session.add(m)
        db.session.commit()
        return admin.id


# _login: realiza login y devuelve el access_token; entradas client, username, password; salida str; efecto secundario autentica.
def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]

# test_export_csv_preview_bom: valida el escenario export csv preview bom preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_export_csv_preview_bom(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/materials/export/preview?format=csv", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["content"].startswith("\ufeff")
    assert "Codigo" in data["content"] or "Código" in data["content"]

# test_export_download_excel: valida el escenario export download excel preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_export_download_excel(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/materials/export/download?format=excel", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.content_type

# test_export_forbidden: valida el escenario export forbidden preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_export_forbidden(client, app):
    _seed(app)
    with app.app_context():
        from app.identity.models import Role, User
        r = Role(name="technician", description="Tecnico")
        db.session.add(r)
        db.session.flush()
        u = User(username="tech", email="tech@test.local")
        u.set_password("Tech123!")
        u.roles.append(r)
        db.session.add(u)
        db.session.commit()
    token = _login(client, "tech", "Tech123!")
    resp = client.get("/api/v1/materials/export/download?format=csv", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
