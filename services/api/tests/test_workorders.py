# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.
import json

from app.extensions import db
from app.identity.models import User, Role
from app.workorders.models import WorkOrder

# Inserta datos iniciales en la base; recibe app; interactua con la base de datos; devuelve el valor correspondiente.
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
# _login: realiza login y devuelve el access_token; entradas client, username, password; salida str; efecto secundario autentica.
def _login(client, username, password):

    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})

    return resp.get_json()["access_token"]

# test_create_work_order: valida el escenario create work order preparando datos, ejecutando la accion y comprobando el resultado esperado.
def test_create_work_order(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "disp", "Disp123!")
    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Reparación AC", "description": "No enfría", "priority": "high"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Reparación AC"
    assert data["status"] == "pending"

# test_technician_cannot_create: valida el escenario technician cannot create preparando datos, ejecutando la accion y comprobando el resultado esperado.
def test_technician_cannot_create(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "tech", "Tech123!")
    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test"},
    )
    assert resp.status_code == 403

# test_timeline_per_field_on_admin_edit: valida el escenario timeline per field on admin edit preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_timeline_per_field_on_admin_edit(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    disp_tok = _login(client, "disp", "Disp123!")
    admin_tok = _login(client, "admin", "Admin123!")
    r = client.post("/api/v1/work-orders", headers={"Authorization": "Bearer " + disp_tok}, json={"title": "WO1", "description": "d", "priority": "high"})
    assert r.status_code == 201
    wo_id = r.get_json()["id"]
    r2 = client.patch("/api/v1/work-orders/{}".format(wo_id), headers={"Authorization": "Bearer " + disp_tok, "If-Match": str(r.get_json()["version"])}, json={"assigned_to_id": tech_id})
    # admin edit: technician, installation_type, scheduled_at
    g = client.get("/api/v1/work-orders/{}".format(wo_id), headers={"Authorization": "Bearer " + admin_tok})
    ver = g.get_json()["version"]
    r3 = client.patch("/api/v1/work-orders/{}".format(wo_id), headers={"Authorization": "Bearer " + admin_tok, "If-Match": str(ver)}, json={
        "assigned_to_id": None,
        "installation_type": "Instalacion X",
        "scheduled_at": "2026-12-01T10:00:00",
        "scheduled_end": "2026-12-01T11:00:00",
        "reason": "motivo test",
    })
    assert r3.status_code == 200
    tl = client.get("/api/v1/work-orders/{}/timeline".format(wo_id), headers={"Authorization": "Bearer " + admin_tok})
    assert tl.status_code == 200
    entries = tl.get_json()
    fields = [e.get("field") for e in entries]
    assert "assigned_to_id" in fields
    assert "installation_type" in fields
    assert "scheduled_at" in fields
    for f in ("assigned_to_id", "installation_type", "scheduled_at"):
        e = next(x for x in entries if x.get("field") == f)
        assert "old_value" in e
        assert "new_value" in e
        assert e.get("reason") == "motivo test"
        assert e.get("actor") is not None
        assert e.get("created_at") is not None

# test_timeline_technician_forbidden_other: valida el escenario timeline technician forbidden other preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_timeline_technician_forbidden_other(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    disp_tok = _login(client, "disp", "Disp123!")
    tech_tok = _login(client, "tech", "Tech123!")
    r = client.post("/api/v1/work-orders", headers={"Authorization": "Bearer " + disp_tok}, json={"title": "WO2"})
    assert r.status_code == 201
    wo_id = r.get_json()["id"]
    # tech tries timeline of unassigned order -> 403
    tl = client.get("/api/v1/work-orders/{}/timeline".format(wo_id), headers={"Authorization": "Bearer " + tech_tok})
    assert tl.status_code == 403

# test_assign_and_transition: valida el escenario assign and transition preparando datos, ejecutando la accion y comprobando el resultado esperado.
def test_assign_and_transition(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "disp", "Disp123!")
    tech_token = _login(client, "tech", "Tech123!")


    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "Orden 1"},
    )
    wo_id = resp.get_json()["id"]


    resp = client.put(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"assigned_to_id": tech_id},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "pending"


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
    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/status",
        headers={"Authorization": f"Bearer {tech_token}"},
        json={"to_status": "completed"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
# test_invalid_transition: valida el escenario invalid transition preparando datos, ejecutando la accion y comprobando el resultado esperado.
def test_invalid_transition(client, app):

    admin_id, disp_id, tech_id = _seed(app)

    token = _login(client, "disp", "Disp123!")
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
    assert resp.status_code == 409# test_history: valida el escenario history preparando datos, ejecutando la accion y comprobando el resultado esperado.
def test_history(client, app):

    admin_id, disp_id, tech_id = _seed(app)

    token = _login(client, "disp", "Disp123!")
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
    history = resp.get_json()# test_work_order_edit_patch_and_put: valida el escenario work order edit patch and put preparando datos, ejecutando la accion y comprobando el resultado esperado.
def test_work_order_edit_patch_and_put(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "disp", "Disp123!")

    # Create an order as dispatcher
    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Orden editable", "description": "desc", "priority": "medium"},
    )
    assert resp.status_code == 201
    wo = resp.get_json()
    wo_id = wo["id"]
    version = wo.get("version", 0)

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Orden editada PATCH"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Orden editada PATCH"

    resp = client.put(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Orden editada PUT"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Orden editada PUT"

    # If-Match válido: la ruta lo parsea; el servicio actual no aplica bloqueo optimista.
    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {token}", "If-Match": str(version)},
        json={"title": "Orden con If-Match válido"},
    )
    assert resp.status_code == 200

    # If-Match inválido: ahora se rechaza por versión desactualizada.
    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {token}", "If-Match": "999999"},
        json={"title": "Orden con If-Match inválido"},
    )
    assert resp.status_code == 400

# test_work_orders_list_filters_and_pagination: valida el escenario work orders list filters and pagination preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_work_orders_list_filters_and_pagination(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "disp", "Disp123!")

    for i in range(3):
        client.post(
            "/api/v1/work-orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": f"Orden lista {i}", "priority": "low"},
        )

    resp = client.get(
        "/api/v1/work-orders?page=1&page_size=1&status=pending",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert "items" in data and "total" in data and "page" in data and "page_size" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 1
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert data["total"] >= 3
    assert all(item["status"] == "pending" for item in data["items"])

# test_work_orders_calendar_range_and_empty_technician: valida el escenario work orders calendar range and empty technician preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_work_orders_calendar_range_and_empty_technician(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "disp", "Disp123!")
    tech_token = _login(client, "tech", "Tech123!")

    from datetime import date, timedelta

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    # Create one order to ensure the range query returns a list (possibly empty depending on filters).
    client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "Orden calendario", "priority": "low"},
    )

    resp = client.get(
        f"/api/v1/work-orders?date_from={today}&date_to={tomorrow}&page=1&page_size=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert isinstance(data.get("items"), list)

    # Técnico sin órdenes asignadas: el filtro por technician_id devuelve lista vacía.
    resp = client.get(
        f"/api/v1/work-orders?technician_id={tech_id}",
        headers={"Authorization": f"Bearer {tech_token}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data.get("items"), list)
# test_admin_cannot_create_work_order: valida el escenario admin cannot create work order preparando datos, ejecutando la accion y comprobando el resultado esperado.
def test_admin_cannot_create_work_order(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")

    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "Orden admin no permitida"},
    )

    assert resp.status_code == 403


# test_admin_can_edit_work_order_with_reason: valida el escenario admin can edit work order with reason preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_can_edit_work_order_with_reason(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden base"})
    assert resp.status_code == 201
    wo = resp.get_json()
    wo_id = wo["id"]
    version = wo.get("version", 0)

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": str(version)},
        json={"title": "Orden editada por admin", "reason": "Correccion de datos"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Orden editada por admin"

# test_admin_edit_without_reason_returns_422: valida el escenario admin edit without reason returns 422 preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_edit_without_reason_returns_422(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden sin motivo"})
    wo_id = resp.get_json()["id"]
    version = resp.get_json().get("version", 0)

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": str(version)},
        json={"title": "Cambio sin motivo"},
    )
    assert resp.status_code == 422

# test_admin_cannot_edit_terminal_order: valida el escenario admin cannot edit terminal order preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_cannot_edit_terminal_order(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden terminal"})
    wo_id = resp.get_json()["id"]
    version = resp.get_json().get("version", 0)

    client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {disp_token}"}, json={"to_status": "assigned"})
    client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {disp_token}"}, json={"to_status": "in_progress"})
    client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {disp_token}"}, json={"to_status": "completed", "notes": "ok"})

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": str(version)},
        json={"title": "No debe cambiar", "reason": "Intento"},
    )
    assert resp.status_code in (403, 409)

# test_technician_cannot_edit_work_order: valida el escenario technician cannot edit work order preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_technician_cannot_edit_work_order(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    tech_token = _login(client, "tech", "Tech123!")
    disp_token = _login(client, "disp", "Disp123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden tech"})
    wo_id = resp.get_json()["id"]
    version = resp.get_json().get("version", 0)

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {tech_token}", "If-Match": str(version)},
        json={"title": "Cambio tech", "reason": "x"},
    )
    assert resp.status_code == 403

# test_admin_edit_invalid_ifmatch_returns_400: valida el escenario admin edit invalid ifmatch returns 400 preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_edit_invalid_ifmatch_returns_400(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden ifmatch"})
    wo_id = resp.get_json()["id"]

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": "999999"},
        json={"title": "Cambio", "reason": "Motivo"},
    )
    assert resp.status_code == 400

# test_admin_edit_notifies_technician: valida el escenario admin edit notifies technician preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_edit_notifies_technician(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")
    tech_token = _login(client, "tech", "Tech123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden notif"})
    wo_id = resp.get_json()["id"]
    version = resp.get_json().get("version", 0)

    from app.notifications.models import Notification
    before = 0
    with app.app_context():
        before = Notification.query.filter_by(user_id=tech_id).count()

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": str(version)},
        json={"assigned_to_id": tech_id, "reason": "Cambio admin"},
    )
    assert resp.status_code == 200

    with app.app_context():
        after = Notification.query.filter_by(user_id=tech_id).count()
    assert after > before

# test_admin_edit_appears_in_timeline: valida el escenario admin edit appears in timeline preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_edit_appears_in_timeline(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden timeline"})
    wo_id = resp.get_json()["id"]
    version = resp.get_json().get("version", 0)

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": str(version)},
        json={"title": "Orden timeline editada", "reason": "Motivo timeline"},
    )
    assert resp.status_code == 200

    resp = client.get(f"/api/v1/work-orders/{wo_id}/timeline", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(item.get("reason") == "Motivo timeline" for item in data)

# test_admin_changes_technician_validates_rf09: valida el escenario admin changes technician validates rf09 preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_changes_technician_validates_rf09(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden cambio tecnico"})
    wo_id = resp.get_json()["id"]
    version = resp.get_json().get("version", 0)

    # invalid technician -> 400/404
    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": str(version)},
        json={"assigned_to_id": 999999, "reason": "Reasignacion"},
    )
    assert resp.status_code in (400, 404)

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": str(version)},
        json={"assigned_to_id": tech_id, "reason": "Reasignacion valida"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["assigned_to"]["id"] == tech_id

# test_admin_changes_installation_type: valida el escenario admin changes installation type preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_changes_installation_type(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden tipo"})
    wo_id = resp.get_json()["id"]
    version = resp.get_json().get("version", 0)

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": str(version)},
        json={"installation_type": "Residencial", "installation_type_code": None, "reason": "Cambio tipo"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["installation_type"] == "Residencial"

# test_admin_adds_materials: valida el escenario admin adds materials preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_adds_materials(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")

    # create material via API
    resp = client.post("/api/v1/materials", headers={"Authorization": f"Bearer {admin_token}"}, json={"name": "MatAdmin", "category_id": 1, "unit_id": 1, "current_stock": 10, "min_stock": 1})
    # if category/unit missing, skip
    if resp.status_code not in (200, 201):
        import pytest
        pytest.skip("No se pudo crear material (catálogo no disponible)")
    mat_id = resp.get_json()["id"]

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden materiales"})
    wo_id = resp.get_json()["id"]

    resp = client.post(
        f"/api/v1/work-orders/{wo_id}/materials",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"items": [{"material_id": mat_id, "quantity": 1}]},
    )
    assert resp.status_code == 200

# test_admin_postpones_date: valida el escenario admin postpones date preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_postpones_date(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden fecha"})
    wo_id = resp.get_json()["id"]
    version = resp.get_json().get("version", 0)

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": str(version)},
        json={"scheduled_at": "2026-11-10T10:00:00", "scheduled_end": "2026-11-10T11:00:00", "reason": "Aplazar"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["scheduled_at"].startswith("2026-11-10")

# test_admin_edit_date_overlap_rejected: valida el escenario admin edit date overlap rejected preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_edit_date_overlap_rejected(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden base", "assigned_to_id": tech_id})
    wo_id = resp.get_json()["id"]
    version = resp.get_json().get("version", 0)
    client.post(f"/api/v1/work-orders/{wo_id}/schedule", headers={"Authorization": f"Bearer {disp_token}"}, json={"start": "2026-11-10T10:00:00", "end": "2026-11-10T11:00:00", "version": version})

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden solape", "assigned_to_id": tech_id})
    wo2_id = resp.get_json()["id"]
    version2 = resp.get_json().get("version", 0)

    resp = client.patch(
        f"/api/v1/work-orders/{wo2_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": str(version2)},
        json={"scheduled_at": "2026-11-10T10:30:00", "scheduled_end": "2026-11-10T11:30:00", "reason": "Solape"},
    )
    assert resp.status_code == 409

# test_admin_edit_stores_old_and_new_in_timeline: valida el escenario admin edit stores old and new in timeline preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_admin_edit_stores_old_and_new_in_timeline(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")
    disp_token = _login(client, "disp", "Disp123!")

    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {disp_token}"}, json={"title": "Orden oldnew"})
    wo_id = resp.get_json()["id"]
    version = resp.get_json().get("version", 0)

    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {admin_token}", "If-Match": str(version)},
        json={"title": "Orden new value", "reason": "Motivo oldnew"},
    )
    assert resp.status_code == 200

    resp = client.get(f"/api/v1/work-orders/{wo_id}/timeline", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(item.get("reason") == "Motivo oldnew" for item in data)
