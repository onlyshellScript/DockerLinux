from app.extensions import db
from app.identity.models import User, Role
from app.materials.models import Material


import os
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in __import__("sys").path:
    __import__("sys").path.insert(0, sys_path)

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


def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]


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


def test_technician_cannot_create_material(client, app):
    _seed(app)
    token = _login(client, "tech", "Tech123!")
    resp = client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test", "unit": "pza"},
    )
    assert resp.status_code == 403


def test_stock_in_and_out(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")

    # Create material
    from app.materials.models import MaterialCatalog
    with app.app_context():
        cid = MaterialCatalog.query.first().id
    resp = client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"catalog_item_id": cid, "current_stock": 0, "min_stock": 0, "unit_price": 5000},
    )
    mat_id = resp.get_json()["id"]

    # Stock IN
    resp = client.post(
        f"/api/v1/materials/{mat_id}/movements",
        headers={"Authorization": f"Bearer {token}"},
        json={"quantity": 20, "movement_type": "IN", "notes": "Compra inicial"},
    )
    assert resp.status_code == 201

    # Verify stock
    resp = client.get(f"/api/v1/materials/{mat_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.get_json()["current_stock"] == 20

    # Stock OUT
    resp = client.post(
        f"/api/v1/materials/{mat_id}/movements",
        headers={"Authorization": f"Bearer {token}"},
        json={"quantity": 5, "movement_type": "OUT"},
    )
    assert resp.status_code == 201

    resp = client.get(f"/api/v1/materials/{mat_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.get_json()["current_stock"] == 15


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

    # List
    resp = client.get("/api/v1/technician-profiles", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1

    # Update availability
    profile_id = data["id"]
    resp = client.put(
        f"/api/v1/technician-profiles/{profile_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_available": False},
    )
    assert resp.status_code == 200
    assert resp.get_json()["is_available"] is False


def test_free_text_rejected(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post("/api/v1/materials", headers={"Authorization": f"Bearer {token}"}, json={"name": "X", "unit": "pza"})
    assert resp.status_code == 422


def test_catalog_item_not_found(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post("/api/v1/materials", headers={"Authorization": f"Bearer {token}"}, json={"catalog_item_id": 999999, "current_stock": 1, "min_stock": 0, "unit_price": 1})
    assert resp.status_code == 422


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
