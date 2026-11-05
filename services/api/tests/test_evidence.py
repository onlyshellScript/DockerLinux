import io

from PIL import Image

from app.extensions import db
from app.identity.models import User, Role


def _png_bytes():
    img = Image.new("RGB", (1, 1), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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


def _create_wo(client, token, assigned_to_id=None):
    payload = {"title": "WO for evidence"}
    if assigned_to_id:
        payload["assigned_to_id"] = assigned_to_id
    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json=payload)
    return resp.get_json()["id"]


def test_upload_observation(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    wo_id = _create_wo(client, token)

    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"category": "ADDITIONAL", "description": "Cliente no estaba en casa"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["description"] == "Cliente no estaba en casa"


def test_upload_photo(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    wo_id = _create_wo(client, token)

    file_data = io.BytesIO(_png_bytes())
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"category": "BEFORE", "file": (file_data, "test.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["original_name"] == "test.png"
    assert data["category"] == "BEFORE"


def test_invalid_extension(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    wo_id = _create_wo(client, token)

    file_data = io.BytesIO(b"fake exe")
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"category": "BEFORE", "file": (file_data, "malware.exe")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_list_evidences(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    wo_id = _create_wo(client, token)

    client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"category": "ADDITIONAL", "description": "Obs 1"},
    )
    client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"category": "ADDITIONAL", "description": "Obs 2"},
    )

    resp = client.get(f"/api/v1/work-orders/{wo_id}/evidences", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2


def test_download_photo(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    wo_id = _create_wo(client, token)

    file_data = io.BytesIO(_png_bytes())
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"category": "BEFORE", "file": (file_data, "photo.png")},
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
        data={"category": "ADDITIONAL", "description": "To delete"},
    )
    ev_id = resp.get_json()["id"]

    resp = client.delete(f"/api/v1/evidences/{ev_id}", headers={"Authorization": f"Bearer {tech_token}"})
    assert resp.status_code == 403

    resp = client.delete(f"/api/v1/evidences/{ev_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200


def test_technician_isolation(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    tech_token = _login(client, "tech", "Tech123!")
    wo_id = _create_wo(client, admin_token, assigned_to_id=tech_id)

    # tech can access assigned
    resp = client.get(f"/api/v1/work-orders/{wo_id}/evidences", headers={"Authorization": f"Bearer {tech_token}"})
    assert resp.status_code == 200

    # another technician cannot
    other = User(username="tech2", email="tech2@test.local")
    # create manually
    with app.app_context():
        tech_role = Role.query.filter_by(name="technician").first()
        other.set_password("Tech123!")
        other.roles.append(tech_role)
        db.session.add(other)
        db.session.commit()
        other_id = other.id
    other_token = _login(client, "tech2", "Tech123!")
    resp = client.get(f"/api/v1/work-orders/{wo_id}/evidences", headers={"Authorization": f"Bearer {other_token}"})
    assert resp.status_code == 403


def test_signature_refusal_and_submit(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    tech_token = _login(client, "tech", "Tech123!")
    wo_id = _create_wo(client, admin_token, assigned_to_id=tech_id)

    file_data = io.BytesIO(_png_bytes())
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {tech_token}"},
        data={"category": "BEFORE", "file": (file_data, "p.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201

    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/signatures",
        headers={"Authorization": f"Bearer {tech_token}"},
        json={"refused": True, "reason": "cliente ausente"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["refused"] is True

    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences/submit",
        headers={"Authorization": f"Bearer {tech_token}"},
        json={},
    )
    assert resp.status_code == 200


def test_submit_incomplete(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    tech_token = _login(client, "tech", "Tech123!")
    wo_id = _create_wo(client, admin_token, assigned_to_id=tech_id)

    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences/submit",
        headers={"Authorization": f"Bearer {tech_token}"},
        json={},
    )
    assert resp.status_code == 400


def test_admin_approve_flow(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    tech_token = _login(client, "tech", "Tech123!")
    wo_id = _create_wo(client, admin_token, assigned_to_id=tech_id)

    file_data = io.BytesIO(_png_bytes())
    client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {tech_token}"},
        data={"category": "BEFORE", "file": (file_data, "p.png")},
        content_type="multipart/form-data",
    )
    client.post(
        f"/api/v1/work-orders/{wo_id}/signatures",
        headers={"Authorization": f"Bearer {tech_token}"},
        json={"refused": True, "reason": "ausente"},
    )
    client.post(f"/api/v1/work-orders/{wo_id}/evidences/submit", headers={"Authorization": f"Bearer {tech_token}"}, json={})

    # admin start review + approve
    r = client.post(f"/api/v1/work-orders/{wo_id}/evidences/start-review", headers={"Authorization": f"Bearer {admin_token}"}, json={})
    assert r.status_code == 200
    r = client.post(f"/api/v1/work-orders/{wo_id}/evidences/approve", headers={"Authorization": f"Bearer {admin_token}"}, json={})
    assert r.status_code == 200

    # technician cannot approve
    r = client.post(f"/api/v1/work-orders/{wo_id}/evidences/approve", headers={"Authorization": f"Bearer {tech_token}"}, json={})
    assert r.status_code == 403