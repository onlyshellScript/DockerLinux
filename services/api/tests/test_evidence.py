import io

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


def _create_wo(client, token):
    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "WO for evidence"},
    )
    return resp.get_json()["id"]


def test_upload_observation(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    wo_id = _create_wo(client, token)

    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"evidence_type": "observation", "description": "Cliente no estaba en casa"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["evidence_type"] == "observation"
    assert data["description"] == "Cliente no estaba en casa"


def test_upload_photo(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    wo_id = _create_wo(client, token)

    file_data = io.BytesIO(b"\x89PNG\r\n\x1a\nfakepng")
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"evidence_type": "photo", "file": (file_data, "test.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["file_name"] == "test.png"
    assert data["evidence_type"] == "photo"


def test_invalid_extension(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    wo_id = _create_wo(client, token)

    file_data = io.BytesIO(b"fake exe")
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"evidence_type": "photo", "file": (file_data, "malware.exe")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "not allowed" in resp.get_json()["error"]


def test_list_evidences(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    wo_id = _create_wo(client, token)

    client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"evidence_type": "observation", "description": "Obs 1"},
    )
    client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"evidence_type": "observation", "description": "Obs 2"},
    )

    resp = client.get(f"/api/v1/work-orders/{wo_id}/evidences", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2


def test_download_photo(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    wo_id = _create_wo(client, token)

    file_data = io.BytesIO(b"\x89PNG\r\n\x1a\nfakepng")
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"evidence_type": "photo", "file": (file_data, "photo.png")},
        content_type="multipart/form-data",
    )
    ev_id = resp.get_json()["id"]

    resp = client.get(f"/api/v1/evidences/{ev_id}/download", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.data.startswith(b"\x89PNG")


def test_only_admin_can_delete(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    tech_token = _login(client, "tech", "Tech123!")
    wo_id = _create_wo(client, admin_token)

    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"evidence_type": "observation", "description": "To delete"},
    )
    ev_id = resp.get_json()["id"]

    resp = client.delete(f"/api/v1/evidences/{ev_id}", headers={"Authorization": f"Bearer {tech_token}"})
    assert resp.status_code == 403

    resp = client.delete(f"/api/v1/evidences/{ev_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
