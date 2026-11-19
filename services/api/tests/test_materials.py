# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.
from app.extensions import db
from app.identity.models import User, Role
from app.materials.models import Material


import os
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in __import__("sys").path:
    __import__("sys").path.insert(0, sys_path)
# Inserta datos iniciales en la base; recibe app; interactua con la base de datos; accede al sistema de archivos; devuelve el valor correspondiente.

def _seed(app):
    from seeds.load_catalog import load_into_app
    cat_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seeds", "materiales_gas_natural.json")
    with app.app_context():
        admin_role = Role(name="admin", description="Administrador")
        disp_role = Role(name="dispatcher", description="Despachador")
        tech_role = Role(name="technician", description="Tecnico")
        db.session.add_all([admin_role, disp_role, tech_role])
        db.session.flush()

        admin = User(username="admin", email="admin@test.local")
        admin.set_password("Admin123!")
        admin.roles.append(admin_role)

        tech = User(username="tech", email="tech@test.local")
        tech.set_password("Tech123!")
        tech.roles.append(tech_role)

        db.session.add_all([admin, tech])
        db.session.commit()
        load_into_app(app, cat_path)
        return admin.id, tech.id


# _login: realiza login y devuelve el access_token; entradas client, username, password; salida str; efecto secundario autentica.
def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]

# test_create_material: valida el escenario create material preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_create_material(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    from app.materials.models import MaterialCatalog
    with app.app_context():
        ci = MaterialCatalog.query.first()
        cid = ci.id
    resp = client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"catalog_item_id": cid, "current_stock": 10, "min_stock": 0, "unit_price": 5000},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["current_stock"] == 10
    assert data["catalog_item_id"] == cid

# test_technician_cannot_create_material: valida el escenario technician cannot create material preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_technician_cannot_create_material(client, app):
    _seed(app)
    token = _login(client, "tech", "Tech123!")
    resp = client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test", "unit": "pza"},
    )
    assert resp.status_code == 403

# test_stock_in_and_out: valida el escenario stock in and out preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_stock_in_and_out(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")

    from app.materials.models import MaterialCatalog
    with app.app_context():
        cid = MaterialCatalog.query.first().id
    resp = client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"catalog_item_id": cid, "current_stock": 0, "min_stock": 0, "unit_price": 5000},
    )
    mat_id = resp.get_json()["id"]

    resp = client.post(
        f"/api/v1/materials/{mat_id}/movements",
        headers={"Authorization": f"Bearer {token}"},
        json={"quantity": 20, "movement_type": "IN", "notes": "Compra inicial"},
    )
    assert resp.status_code == 201

    resp = client.get(f"/api/v1/materials/{mat_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.get_json()["current_stock"] == 20

    resp = client.post(
        f"/api/v1/materials/{mat_id}/movements",
        headers={"Authorization": f"Bearer {token}"},
        json={"quantity": 5, "movement_type": "OUT"},
    )
    assert resp.status_code == 201

    resp = client.get(f"/api/v1/materials/{mat_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.get_json()["current_stock"] == 15

# test_insufficient_stock: valida el escenario insufficient stock preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_insufficient_stock(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")

    from app.materials.models import MaterialCatalog
    with app.app_context():
        cid = MaterialCatalog.query.first().id
    resp = client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"catalog_item_id": cid, "current_stock": 3, "min_stock": 0, "unit_price": 5000},
    )
    mat_id = resp.get_json()["id"]

    resp = client.post(
        f"/api/v1/materials/{mat_id}/movements",
        headers={"Authorization": f"Bearer {token}"},
        json={"quantity": 10, "movement_type": "OUT"},
    )
    assert resp.status_code == 409
    assert "insufficient" in resp.get_json()["error"]

# test_movements_history: valida el escenario movements history preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_movements_history(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")

    from app.materials.models import MaterialCatalog
    with app.app_context():
        cid = MaterialCatalog.query.first().id
    resp = client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"catalog_item_id": cid, "current_stock": 0, "min_stock": 0, "unit_price": 5000},
    )
    mat_id = resp.get_json()["id"]

    client.post(
        f"/api/v1/materials/{mat_id}/movements",
        headers={"Authorization": f"Bearer {token}"},
        json={"quantity": 100, "movement_type": "IN"},
    )
    client.post(
        f"/api/v1/materials/{mat_id}/movements",
        headers={"Authorization": f"Bearer {token}"},
        json={"quantity": 20, "movement_type": "OUT"},
    )

    resp = client.get(f"/api/v1/materials/{mat_id}/movements", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    movements = resp.get_json()
    assert len(movements) == 2

# test_technician_profile: valida el escenario technician profile preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_technician_profile(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")

    resp = client.post(
        "/api/v1/technician-profiles",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": tech_id, "phone": "3001234567", "specialty": "HVAC"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["phone"] == "3001234567"
    assert data["specialty"] == "HVAC"

    resp = client.get("/api/v1/technician-profiles", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1

    profile_id = data["id"]
    resp = client.put(
        f"/api/v1/technician-profiles/{profile_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_available": False},
    )
    assert resp.status_code == 200
    assert resp.get_json()["is_available"] is False

# test_free_text_rejected: valida el escenario free text rejected preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_free_text_rejected(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post("/api/v1/materials", headers={"Authorization": f"Bearer {token}"}, json={"name": "X", "unit": "pza"})
    assert resp.status_code == 422

# test_catalog_item_not_found: valida el escenario catalog item not found preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_catalog_item_not_found(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post("/api/v1/materials", headers={"Authorization": f"Bearer {token}"}, json={"catalog_item_id": 999999, "current_stock": 1, "min_stock": 0, "unit_price": 1})
    assert resp.status_code == 422

# test_duplicate_catalog_item: valida el escenario duplicate catalog item preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_duplicate_catalog_item(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    from app.materials.models import MaterialCatalog
    with app.app_context():
        cid = MaterialCatalog.query.first().id
    r1 = client.post("/api/v1/materials", headers={"Authorization": f"Bearer {token}"}, json={"catalog_item_id": cid, "current_stock": 1, "min_stock": 0, "unit_price": 1})
    assert r1.status_code == 201
    r2 = client.post("/api/v1/materials", headers={"Authorization": f"Bearer {token}"}, json={"catalog_item_id": cid, "current_stock": 1, "min_stock": 0, "unit_price": 1})
    assert r2.status_code == 409

# test_decimal_precision_unit: valida el escenario decimal precision unit preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_decimal_precision_unit(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    from app.materials.models import MaterialCatalog, MaterialUnit
    with app.app_context():
        # find a unit that does not allow decimal
        u = MaterialUnit.query.filter_by(allows_decimal=False).first()
        ci = MaterialCatalog.query.filter_by(unit_id=u.id).first()
        cid = ci.id
    # fractional stock on non-decimal unit -> 422
    r = client.post("/api/v1/materials", headers={"Authorization": f"Bearer {token}"}, json={"catalog_item_id": cid, "current_stock": 1.5, "min_stock": 0, "unit_price": 1})
    assert r.status_code == 422

# Crea el registro solicitado con los datos recibidos; recibe app, admin_id; interactua con la base de datos; devuelve el valor correspondiente.

def _create_inherited(app, admin_id):
    from app.materials.models import Material, StockMovement
    with app.app_context():
        m = Material(name="Heredado", code="HER-1", unit="pza", current_stock=7, min_stock=2, unit_price=100, is_active=True, catalog_item_id=None)
        db.session.add(m)
        db.session.flush()
        db.session.add(StockMovement(material_id=m.id, quantity=7, movement_type="ADJUSTMENT", user_id=admin_id, notes="Saldo inicial"))
        db.session.commit()
        return m.id

# test_link_catalog_success: valida el escenario link catalog success preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_link_catalog_success(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    mid = _create_inherited(app, admin_id)
    from app.materials.models import MaterialCatalog
    with app.app_context():
        # pick a catalog item not inventoried
        inv = {m.catalog_item_id for m in Material.query.filter(Material.catalog_item_id.isnot(None)).all()}
        ci = MaterialCatalog.query.filter(~MaterialCatalog.id.in_(inv) if inv else True).first()
        cid = ci.id
        old_stock = 7
        old_price = 100
    from app.materials.models import StockMovement
    with app.app_context():
        mv_before = StockMovement.query.filter_by(material_id=mid).count()
    r = client.put(f"/api/v1/materials/{mid}", headers={"Authorization": f"Bearer {token}"}, json={"catalog_item_id": cid})
    assert r.status_code == 200
    with app.app_context():
        m = Material.query.get(mid)
        assert m.id == mid
        assert m.catalog_item_id == cid
        assert float(m.current_stock) == old_stock
        assert float(m.unit_price) == old_price
        mv_after = StockMovement.query.filter_by(material_id=mid).count()
        assert mv_after == mv_before

# test_link_catalog_already_inventoried: valida el escenario link catalog already inventoried preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_link_catalog_already_inventoried(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    from app.materials.models import MaterialCatalog, Material
    with app.app_context():
        ci = MaterialCatalog.query.first()
        m1 = Material(name=ci.name, code=ci.code, unit="pza", current_stock=1, min_stock=0, unit_price=1, catalog_item_id=ci.id)
        db.session.add(m1); db.session.commit()
        m = Material(name="H2", code="H2", unit="pza", current_stock=1, min_stock=0, unit_price=1, catalog_item_id=None)
        db.session.add(m); db.session.commit()
        cid = ci.id
        mid = m.id
    r = client.put(f"/api/v1/materials/{mid}", headers={"Authorization": f"Bearer {token}"}, json={"catalog_item_id": cid})
    assert r.status_code == 409

# test_link_catalog_not_found: valida el escenario link catalog not found preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_link_catalog_not_found(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    mid = _create_inherited(app, admin_id)
    r = client.put(f"/api/v1/materials/{mid}", headers={"Authorization": f"Bearer {token}"}, json={"catalog_item_id": 999999})
    assert r.status_code == 422

# test_link_catalog_forbidden: valida el escenario link catalog forbidden preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_link_catalog_forbidden(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "tech", "Tech123!")
    mid = _create_inherited(app, admin_id)
    from app.materials.models import MaterialCatalog
    with app.app_context():
        inv = {m.catalog_item_id for m in Material.query.filter(Material.catalog_item_id.isnot(None)).all()}
        ci = MaterialCatalog.query.filter(~MaterialCatalog.id.in_(inv) if inv else True).first()
        cid = ci.id
    r = client.put(f"/api/v1/materials/{mid}", headers={"Authorization": f"Bearer {token}"}, json={"catalog_item_id": cid})
    assert r.status_code == 403
