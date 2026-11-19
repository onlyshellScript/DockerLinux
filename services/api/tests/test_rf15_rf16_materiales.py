# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.

from app.extensions import db
from app.identity.models import User, Role
from app.materials.models import Material
from app.workorders.models import WorkOrder

# Inserta datos iniciales en la base; recibe app; interactua con la base de datos; devuelve el valor correspondiente.

def _seed(app):
    with app.app_context():
        admin_role = Role(name="admin", description="Administrador")
        db.session.add(admin_role)
        db.session.flush()
        admin = User(username="admin", email="admin@test.local")
        admin.set_password("Admin123!")
        admin.roles.append(admin_role)
        db.session.add(admin)
        db.session.flush()
        wo = WorkOrder(title="O", created_by_id=admin.id, status="pending", priority="medium")
        db.session.add(wo)
        db.session.flush()
        mat = Material(name="Mat", code="M1", unit="unidad", current_stock=10, min_stock=1, is_active=True)
        db.session.add(mat)
        db.session.commit()
        return admin.id, wo.id, mat.id


# _login: realiza login y devuelve el access_token; entradas client, username, password; salida str; efecto secundario autentica.
def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]

# test_rf15_cantidad_invalida: valida el escenario rf15 cantidad invalida preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf15_cantidad_invalida(client, app):
    admin_id, wo_id, mat_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post(f"/api/v1/materials/{mat_id}/movements", headers={"Authorization": f"Bearer {token}"}, json={"quantity": 0, "movement_type": "CONSUMPTION", "work_order_id": wo_id})
    assert resp.status_code in (400, 422)

# test_rf15_material_inexistente: valida el escenario rf15 material inexistente preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf15_material_inexistente(client, app):
    admin_id, wo_id, mat_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post("/api/v1/materials/999999/movements", headers={"Authorization": f"Bearer {token}"}, json={"quantity": 1, "movement_type": "CONSUMPTION", "work_order_id": wo_id})
    assert resp.status_code == 404

# test_rf15_asociacion_orden_material: valida el escenario rf15 asociacion orden material preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf15_asociacion_orden_material(client, app):
    admin_id, wo_id, mat_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post(f"/api/v1/materials/{mat_id}/movements", headers={"Authorization": f"Bearer {token}"}, json={"quantity": 2, "movement_type": "CONSUMPTION", "work_order_id": wo_id})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["work_order_id"] == wo_id

# test_rf16_descuenta_stock_y_movimiento: valida el escenario rf16 descuenta stock y movimiento preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf16_descuenta_stock_y_movimiento(client, app):
    admin_id, wo_id, mat_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post(f"/api/v1/materials/{mat_id}/movements", headers={"Authorization": f"Bearer {token}"}, json={"quantity": 3, "movement_type": "CONSUMPTION", "work_order_id": wo_id})
    assert resp.status_code == 201
    with app.app_context():
        m = db.session.get(Material, mat_id)
        assert m.current_stock == 7

# test_rf16_rechaza_stock_insuficiente: valida el escenario rf16 rechaza stock insuficiente preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf16_rechaza_stock_insuficiente(client, app):
    admin_id, wo_id, mat_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    resp = client.post(f"/api/v1/materials/{mat_id}/movements", headers={"Authorization": f"Bearer {token}"}, json={"quantity": 100, "movement_type": "CONSUMPTION", "work_order_id": wo_id})
    assert resp.status_code in (400, 409)
    with app.app_context():
        m = db.session.get(Material, mat_id)
        assert m.current_stock == 10


import threading
# test_rf16_concurrencia_sin_stock_negativo: valida el escenario rf16 concurrencia sin stock negativo preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rf16_concurrencia_sin_stock_negativo(client, app):
    admin_id, wo_id, mat_id = _seed(app)
    token = _login(client, "admin", "Admin123!")
    results = []

    def worker():
        r = client.post(f"/api/v1/materials/{mat_id}/movements", headers={"Authorization": f"Bearer {token}"}, json={"quantity": 6, "movement_type": "CONSUMPTION", "work_order_id": wo_id})
        results.append(r.status_code)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start(); t2.start()
    t1.join(); t2.join()

    with app.app_context():
        m = db.session.get(Material, mat_id)
        assert m.current_stock >= 0
