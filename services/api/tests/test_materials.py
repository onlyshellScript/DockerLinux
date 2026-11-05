from app.extensions import db
from app.identity.models import User, Role
from app.materials.models import Material


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

        tech = User(username="tech", email="tech@test.local")
        tech.set_password("Tech123!")
        tech.roles.append(tech_role)

        db.session.add_all([admin, tech])
        db.session.commit()
        return admin.id, tech.id


def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]


def test_create_material(client, app):
    _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Filtro de aire", "code": "FILTRO-AIRE", "unit": "pza", "current_stock": 10, "unit_price": 5000},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "Filtro de aire"
    assert data["current_stock"] == 10


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
    resp = client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Refrigerante", "code": "REFRIG", "unit": "lt", "current_stock": 0},
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

    resp = client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Tornillo", "code": "TORN", "unit": "pza", "current_stock": 3},
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

    resp = client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Cable", "code": "CABLE", "unit": "m", "current_stock": 0},
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
