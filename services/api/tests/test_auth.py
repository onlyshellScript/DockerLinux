import json

from app.extensions import db
from app.identity.models import User, Role


def _seed(app):
    with app.app_context():
        role = Role(name="admin", description="Administrador")
        db.session.add(role)
        user = User(username="admin", email="admin@test.local")
        user.set_password("Admin123!")
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()


def test_login_success(client, app):
    _seed(app)
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["username"] == "admin"


def test_login_wrong_password(client, app):
    _seed(app)
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/api/v1/auth/login", json={})
    assert resp.status_code == 400


def test_refresh_token(client, app):
    _seed(app)
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
    refresh_token = login.get_json()["refresh_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()


def test_users_list_requires_auth(client):
    resp = client.get("/api/v1/users")
    assert resp.status_code == 401


def test_users_list_requires_admin(client, app):
    _seed(app)
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
    token = login.get_json()["access_token"]
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    users = resp.get_json()
    assert len(users) == 1
    assert users[0]["username"] == "admin"


def test_create_user(client, app):
    _seed(app)
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
    token = login.get_json()["access_token"]
    resp = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "tech1", "email": "tech1@test.local", "password": "Tech123!", "role_names": ["admin"]},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "tech1"


def test_non_admin_cannot_list_users(client, app):
    with app.app_context():
        role = Role(name="technician", description="Técnico")
        db.session.add(role)
        user = User(username="tech", email="tech@test.local")
        user.set_password("Tech123!")
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()
    login = client.post("/api/v1/auth/login", json={"username": "tech", "password": "Tech123!"})
    token = login.get_json()["access_token"]
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
