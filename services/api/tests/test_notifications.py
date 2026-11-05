from app.extensions import db
from app.identity.models import User, Role
from app.notifications.models import Notification, STATUS_PENDING


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


def test_create_notification(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": tech_id, "channel": "email", "recipient": "tech@test.local", "message": "Nueva orden asignada"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "pending"
    assert data["channel"] == "email"


def test_invalid_channel(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": tech_id, "channel": "sms", "recipient": "300", "message": "test"},
    )
    assert resp.status_code == 400


def test_technician_cannot_create(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "tech", "Tech123!")
    resp = client.post(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": tech_id, "channel": "email", "recipient": "x@test.local", "message": "test"},
    )
    assert resp.status_code == 403


def test_list_own_notifications(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    tech_token = _login(client, "tech", "Tech123!")

    client.post(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": tech_id, "channel": "email", "recipient": "tech@test.local", "message": "For tech"},
    )
    client.post(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": admin_id, "channel": "email", "recipient": "admin@test.local", "message": "For admin"},
    )

    resp = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {tech_token}"})
    notifications = resp.get_json()
    assert len(notifications) == 1
    assert notifications[0]["message"] == "For tech"


def test_admin_sees_all(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")

    client.post(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": tech_id, "channel": "email", "recipient": "tech@test.local", "message": "For tech"},
    )

    resp = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.get_json()) >= 1


def test_process_pending_no_smtp(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")

    client.post(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": tech_id, "channel": "email", "recipient": "tech@test.local", "message": "Test"},
    )

    resp = client.post("/api/v1/notifications/process", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["processed"] >= 1
