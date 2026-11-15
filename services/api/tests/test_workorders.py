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
    admin_token = _login(client, "disp", "Disp123!")
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
    assert resp.status_code == 409
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
    history = resp.get_json()
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

    # PATCH updates title
    resp = client.patch(
        f"/api/v1/work-orders/{wo_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Orden editada PATCH"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Orden editada PATCH"

    # PUT updates title
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
def test_admin_cannot_create_work_order(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    admin_token = _login(client, "admin", "Admin123!")

    resp = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "Orden admin no permitida"},
    )

    assert resp.status_code == 403



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
    assert any("Motivo timeline" in str(item.get("notes", "")) for item in data)
