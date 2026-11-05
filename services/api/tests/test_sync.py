import json
import uuid

from app.extensions import db
from app.identity.models import User, Role


def _seed(app):
    with app.app_context():
        admin_role = Role(name="admin", description="Administrador")
        tech_role = Role(name="technician", description="Tecnico")
        db.session.add_all([admin_role, tech_role])
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


def test_push_change_status(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")

    # Create WO and assign
    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "WO for sync"},
    )
    wo_id = resp.get_json()["id"]
    client.put(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"assigned_to_id": tech_id},
    )
    client.post(
        f"/api/v1/work-orders/{wo_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"to_status": "assigned"},
    )

    # Tech pushes change_status offline operation
    tech_token = _login(client, "tech", "Tech123!")
    op_id = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/sync/push",
        headers={"Authorization": f"Bearer {tech_token}"},
        json={"operations": [{
            "client_operation_id": op_id,
            "operation_type": "change_status",
            "payload": {"work_order_id": wo_id, "to_status": "in_progress"},
        }]},
    )
    assert resp.status_code == 200
    results = resp.get_json()["results"]
    assert results[0]["status"] == "synced"


def test_push_idempotent(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "WO idempotent"},
    )
    wo_id = resp.get_json()["id"]

    op_id = str(uuid.uuid4())
    body = {"operations": [{
        "client_operation_id": op_id,
        "operation_type": "add_observation",
        "payload": {"work_order_id": wo_id, "description": "Obs from offline"},
    }]}

    resp1 = client.post("/api/v1/sync/push", headers={"Authorization": f"Bearer {admin_token}"}, json=body)
    assert resp1.get_json()["results"][0]["status"] == "synced"

    resp2 = client.post("/api/v1/sync/push", headers={"Authorization": f"Bearer {admin_token}"}, json=body)
    assert resp2.get_json()["results"][0]["status"] == "duplicate"


def test_push_unknown_type(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    op_id = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/sync/push",
        headers={"Authorization": f"Bearer {token}"},
        json={"operations": [{
            "client_operation_id": op_id,
            "operation_type": "unknown",
            "payload": {},
        }]},
    )
    assert resp.status_code == 200
    assert resp.get_json()["results"][0]["status"] == "failed"


def test_pull_changes(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")

    client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "WO pull test"},
    )
    client.post(
        "/api/v1/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Material pull", "unit": "pza"},
    )

    resp = client.get("/api/v1/sync/pull", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "server_time" in data
    assert len(data["work_orders"]) >= 1
    assert len(data["materials"]) >= 1


def test_push_batch_limit(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    ops = [{"client_operation_id": str(uuid.uuid4()), "operation_type": "x", "payload": {}} for _ in range(101)]
    resp = client.post("/api/v1/sync/push", headers={"Authorization": f"Bearer {token}"}, json={"operations": ops})
    assert resp.status_code == 400
