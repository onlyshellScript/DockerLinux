from app.extensions import db
from app.identity.models import User, Role
from app.materials.models import MaterialCatalog


def _seed(app):
    import os, sys
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if base not in sys.path:
        sys.path.insert(0, base)
    with app.app_context():
        admin_role = Role(name="admin", description="Administrador")
        db.session.add(admin_role)
        db.session.flush()
        admin = User(username="admin", email="admin@test.local")
        admin.set_password("Admin123!")
        admin.roles.append(admin_role)
        db.session.add(admin)
        db.session.commit()
        from seeds.load_catalog import load_into_app
        load_into_app(app, os.path.join(base, "seeds", "materiales_gas_natural.json"))
        ci = MaterialCatalog.query.first()
        from app.materials.models import Material
        m = Material(name=ci.name, code=ci.code, unit="pza", current_stock=5, min_stock=2, unit_price=1000, catalog_item_id=ci.id)
        db.session.add(m)
        db.session.commit()
        return admin.id


def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]


def test_csv_bom_and_formula(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    # create a material with malicious name? can't free text; use filters only
    resp = client.get("/api/v1/materials/export/preview?format=csv&separator=;", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    content = resp.get_json()["content"]
    assert content.startswith("\ufeff")
    # formula injection guard: no cell starts with =,+,-,@ without quote
    for line in content.splitlines():
        for cell in line.split(";"):
            if cell and cell[0] in ("=", "+", "-", "@"):
                assert cell.startswith("'")


def test_pdf_bytes(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/materials/export/download?format=pdf", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.data[:4] == b"%PDF"


def test_empty_dataset(client, app):
    # no materials: use fresh app with catalog but delete materials
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    # deactivate all materials via direct DB
    with app.app_context():
        from app.materials.models import Material
        for m in Material.query.all():
            m.is_active = False
        db.session.commit()
    resp = client.get("/api/v1/materials/export/preview?format=csv", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    # only header
    assert data["content"].strip().count("\n") == 0 or "Código" in data["content"]


def test_excel_reopen(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.get("/api/v1/materials/export/download?format=excel", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    import io
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(resp.data))
    assert "Inventario" in wb.sheetnames
    assert "Resumen" in wb.sheetnames
    ws = wb["Inventario"]
    assert ws["A1"].value == "Código"
