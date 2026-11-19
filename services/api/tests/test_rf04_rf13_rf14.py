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
        tech_role = Role(name="technician", description="Tecnico")
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

# test_rf04_cancelar_exige_motivo: valida el escenario rf04 cancelar exige motivo preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf04_cancelar_exige_motivo(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "disp", "Disp123!")
    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json={"title": "O1"})
    wo_id = resp.get_json()["id"]
    resp = client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "cancelled"})
    assert resp.status_code in (400, 422, 409)

# test_rf04_cancelar_desde_estados_validos: valida el escenario rf04 cancelar desde estados validos preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf04_cancelar_desde_estados_validos(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "disp", "Disp123!")
    tech_token = _login(client, "tech", "Tech123!")
    for target in ("assigned", "in_progress"):
        resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json={"title": "O"})
        wo_id = resp.get_json()["id"]
        # move to target via transitions
        if target == "assigned":
            client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "assigned"})
        else:
            client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "assigned"})
            client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "in_progress"})
        resp = client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "cancelled", "reason": "motivo"})
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "cancelled"
        assert resp.get_json()["cancel_reason"] == "motivo"

# test_rf04_cancelar_desde_completada_rechazado: valida el escenario rf04 cancelar desde completada rechazado preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf04_cancelar_desde_completada_rechazado(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "disp", "Disp123!")
    tech_token = _login(client, "tech", "Tech123!")
    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json={"title": "O"})
    wo_id = resp.get_json()["id"]
    client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "assigned"})
    client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "in_progress"})
    client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "completed"})
    resp = client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "cancelled", "reason": "motivo"})
    assert resp.status_code == 409

# test_rf04_cancelar_genera_historial: valida el escenario rf04 cancelar genera historial preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf04_cancelar_genera_historial(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "disp", "Disp123!")
    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json={"title": "O"})
    wo_id = resp.get_json()["id"]
    client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "cancelled", "reason": "motivo"})
    hist = client.get(f"/api/v1/work-orders/{wo_id}/history", headers={"Authorization": f"Bearer {token}"}).get_json()
    assert any(h["to_status"] == "cancelled" and (h.get("notes") == "motivo" or h.get("notes") == "motivo") for h in hist)

# test_rf13_historial_por_transicion: valida el escenario rf13 historial por transicion preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf13_historial_por_transicion(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "disp", "Disp123!")
    tech_token = _login(client, "tech", "Tech123!")
    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json={"title": "O"})
    wo_id = resp.get_json()["id"]
    client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "assigned"})
    client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "in_progress"})
    client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "completed"})
    hist = client.get(f"/api/v1/work-orders/{wo_id}/history", headers={"Authorization": f"Bearer {token}"}).get_json()
    tos = [h["to_status"] for h in hist]
    assert "assigned" in tos and "in_progress" in tos and "completed" in tos

# test_rf13_transicion_invalida_rechazada: valida el escenario rf13 transicion invalida rechazada preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf13_transicion_invalida_rechazada(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "disp", "Disp123!")
    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json={"title": "O"})
    wo_id = resp.get_json()["id"]
    resp = client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "completed"})
    assert resp.status_code == 409

# test_rf14_timeline_cronologico: valida el escenario rf14 timeline cronologico preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf14_timeline_cronologico(client, app):
    admin_id, disp_id, tech_id = _seed(app)
    token = _login(client, "disp", "Disp123!")
    resp = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json={"title": "O"})
    wo_id = resp.get_json()["id"]
    client.post(f"/api/v1/work-orders/{wo_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"to_status": "cancelled", "reason": "r"})
    hist = client.get(f"/api/v1/work-orders/{wo_id}/timeline", headers={"Authorization": f"Bearer {token}"}).get_json()
    dates = [h["created_at"] for h in hist]
    assert dates == sorted(dates)
