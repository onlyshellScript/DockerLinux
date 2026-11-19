# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.
import io

from PIL import Image

from app.extensions import db
from app.identity.models import User, Role


# genera un PNG minimo de 1x1 en bytes para pruebas de carga de evidencia; sin parametros; salida bytes; sin efectos secundarios adicionales.
def _png_bytes():
    img = Image.new("RGB", (1, 1), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# _signature_png_b64: firma de prueba (lienzo transparente con un trazo) codificada como data URL.
def _signature_data_url():
    import base64
    from PIL import ImageDraw
    img = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
    ImageDraw.Draw(img).line([(20, 70), (120, 20), (280, 60)], fill=(20, 20, 20, 255), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

# Inserta datos iniciales en la base; recibe app; interactua con la base de datos; devuelve el valor correspondiente.

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

        disp_role = Role(name="dispatcher", description="Despachador")
        db.session.add(disp_role)
        db.session.flush()
        disp = User(username="disp", email="disp@test.local")
        disp.set_password("Disp123!")
        disp.roles.append(disp_role)

        db.session.add_all([admin, tech, disp])
        db.session.commit()
        return admin.id, tech.id


# _login: realiza login y devuelve el access_token; entradas client, username, password; salida str; efecto secundario autentica.
def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]

# _tech_login: login del tecnico de prueba con su firma de perfil ya registrada (requisito para adjuntar evidencias).
def _tech_login(client, username="tech", password="Tech123!"):
    token = _login(client, username, password)
    r = client.post("/api/v1/me/signature", headers={"Authorization": f"Bearer {token}"}, json={"image": _signature_data_url()})
    assert r.status_code == 201
    return token

# Crea el registro solicitado con los datos recibidos; recibe client, token, assigned_to_id; realiza llamadas de red; devuelve el valor correspondiente.

def _create_wo(client, token, assigned_to_id=None):
    payload = {"title": "WO for evidence"}
    if assigned_to_id:
        payload["assigned_to_id"] = assigned_to_id
    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json=payload)
    return resp.get_json()["id"]

# test_upload_observation: valida el escenario upload observation preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_upload_observation(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")
    wo_id = _create_wo(client, disp_token)

    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"category": "ADDITIONAL", "description": "Cliente no estaba en casa"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["description"] == "Cliente no estaba en casa"

# test_upload_photo: valida el escenario upload photo preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_upload_photo(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")
    wo_id = _create_wo(client, disp_token)

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

# test_invalid_extension: valida el escenario invalid extension preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_invalid_extension(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")
    wo_id = _create_wo(client, disp_token)

    file_data = io.BytesIO(b"fake exe")
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {token}"},
        data={"category": "BEFORE", "file": (file_data, "malware.exe")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400

# test_list_evidences: valida el escenario list evidences preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_list_evidences(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")
    wo_id = _create_wo(client, disp_token)

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

# test_download_photo: valida el escenario download photo preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_download_photo(client, app):
    admin_id, tech_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")
    wo_id = _create_wo(client, disp_token)

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

# test_only_admin_can_delete: valida el escenario only admin can delete preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_only_admin_can_delete(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")
    tech_token = _tech_login(client)
    wo_id = _create_wo(client, disp_token)

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

# test_technician_isolation: valida el escenario technician isolation preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_technician_isolation(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")
    tech_token = _tech_login(client)
    wo_id = _create_wo(client, disp_token, assigned_to_id=tech_id)

    # tech can access assigned
    resp = client.get(f"/api/v1/work-orders/{wo_id}/evidences", headers={"Authorization": f"Bearer {tech_token}"})
    assert resp.status_code == 200

    other = User(username="tech2", email="tech2@test.local")
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

# test_signature_refusal_and_submit: valida el escenario signature refusal and submit preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_signature_refusal_and_submit(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")
    tech_token = _login(client, "tech", "Tech123!")
    wo_id = _create_wo(client, disp_token, assigned_to_id=tech_id)

    # Sin firma de perfil el tecnico no puede adjuntar evidencias.
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {tech_token}"},
        data={"category": "BEFORE", "file": (io.BytesIO(_png_bytes()), "p.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 409 and resp.get_json()["code"] == "technician_signature_required"
    assert client.post("/api/v1/me/signature", headers={"Authorization": f"Bearer {tech_token}"},
                       json={"image": _signature_data_url()}).status_code == 201

    file_data = io.BytesIO(_png_bytes())
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences",
        headers={"Authorization": f"Bearer {tech_token}"},
        data={"category": "BEFORE", "file": (file_data, "p.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    assert resp.get_json()["technician_signature"]["technician_id"] == tech_id

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

# test_submit_incomplete: valida el escenario submit incomplete preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_submit_incomplete(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")
    tech_token = _tech_login(client)
    wo_id = _create_wo(client, disp_token, assigned_to_id=tech_id)

    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/evidences/submit",
        headers={"Authorization": f"Bearer {tech_token}"},
        json={},
    )
    assert resp.status_code == 400

# test_admin_approve_flow: valida el escenario admin approve flow preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_approve_flow(client, app):
    admin_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")
    tech_token = _tech_login(client)
    wo_id = _create_wo(client, disp_token, assigned_to_id=tech_id)

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

    r = client.post(f"/api/v1/work-orders/{wo_id}/evidences/approve", headers={"Authorization": f"Bearer {tech_token}"}, json={})
    assert r.status_code == 403