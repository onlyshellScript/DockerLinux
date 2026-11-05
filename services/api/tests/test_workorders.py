import json

from app.extensions import db
from app.identity.models import User, Role
from app.workorders.models import WorkOrder


def _seed(app):
    with app.app_context():
        admin_role = Role(name="admin", description="Administrador")
        disp_role = Role(name="dispatcher", description="Despachador")
        tech_role = Role(name="technician", description="Técnico")
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
        db.session.commit()
        return admin.id, disp.id, tech.id


def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]


def test_create_work_order(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Reparación AC", "description": "No enfría", "priority": "high"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Reparación AC"
    assert data["status"] == "pending"


def test_technician_cannot_create(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "tech", "Tech123!")
    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test"},
    )
    assert resp.status_code == 403


def test_assign_and_transition(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    tech_token = _login(client, "tech", "Tech123!")

    # Create
    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "Orden 1"},
    )
    wo_id = resp.get_json()["id"]

    # Assign
    resp = client.put(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"assigned_to_id": tech_id},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "pending"

    # Change to assigned
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"to_status": "assigned"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "assigned"

    # Technician moves to in_progress
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/status",
        headers={"Authorization": f"Bearer {tech_token}"},
        json={"to_status": "in_progress"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "in_progress"

    # Technician completes
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/status",
        headers={"Authorization": f"Bearer {tech_token}"},
        json={"to_status": "completed"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"

    # Admin closes
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"to_status": "closed"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "closed"


def test_invalid_transition(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Orden 2"},
    )
    wo_id = resp.get_json()["id"]

    # pending -> in_progress is invalid
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"to_status": "in_progress"},
    )
    assert resp.status_code == 409


def test_history(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Orden 3"},
    )
    wo_id = resp.get_json()["id"]

    resp = client.get(
        f"/api/v1/work-orders/{wo_id}/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    history = resp.get_json()
    assert len(history) >= 1
    assert history[0]["to_status"] == "pending"
