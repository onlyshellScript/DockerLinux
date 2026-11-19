# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.
import os
import sys
import threading
import time

import pytest

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base not in sys.path:
    sys.path.insert(0, base)

from app.extensions import db
from app.identity.models import User, Role
from app.materials.models import Material, MaterialCatalog, StockMovement

# Inserta datos iniciales en la base; recibe app; interactua con la base de datos; accede al sistema de archivos; devuelve el valor correspondiente.

def _seed(app):
    with app.app_context():
        admin_role = Role(name="admin", description="Administrador")
        db.session.add(admin_role)
        db.session.flush()
        admin = User(username="admin", email="admin@test.local")
        admin.set_password("Admin123!")
        admin.roles.append(admin_role)
        db.session.add(admin)
        db.session.commit()
        from seeds.load_catalog import load_into_app
        load_into_app(app, os.path.join(base, "seeds", "materiales_gas_natural.json"))
        ci = MaterialCatalog.query.first()
        m = Material(name=ci.name, code=ci.code, unit="pza", current_stock=10, min_stock=2, unit_price=1000, catalog_item_id=ci.id)
        db.session.add(m)
        db.session.commit()
        return admin.id, m.id


# _login: realiza login y devuelve el access_token; entradas client, username, password; salida str; efecto secundario autentica.
def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]


# test_concurrent_out: valida el escenario concurrent out preparando datos, ejecutando la accion y comprobando el resultado esperado.
@pytest.mark.sqlserver
def test_concurrent_out(sqlserver_client, sqlserver_app):
    admin_id, mat_id = _seed(sqlserver_app)
    token = _login(sqlserver_client, "admin", "Admin123!")
    results = []
# Gestiona worker; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.

    def worker():
        c = sqlserver_app.test_client()
        r = c.post(f"/api/v1/materials/{mat_id}/movements",
                   headers={"Authorization": f"Bearer {token}"},
                   json={"quantity": 6, "movement_type": "OUT"})
        results.append(r.status_code)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start(); time.sleep(0.1); t2.start()
    t1.join(); t2.join()

    assert sorted(results) == [201, 409] or sorted(results) == [409, 201]
    with sqlserver_app.app_context():
        m = Material.query.get(mat_id)
        assert float(m.current_stock) == 4.0
        moves = StockMovement.query.filter_by(material_id=mat_id, movement_type="OUT").count()
        assert moves == 1


# test_concurrent_in: valida el escenario concurrent in preparando datos, ejecutando la accion y comprobando el resultado esperado.
@pytest.mark.sqlserver
def test_concurrent_in(sqlserver_client, sqlserver_app):
    admin_id, mat_id = _seed(sqlserver_app)
    token = _login(sqlserver_client, "admin", "Admin123!")
    results = []
# Gestiona worker; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.

    def worker():
        c = sqlserver_app.test_client()
        r = c.post(f"/api/v1/materials/{mat_id}/movements",
                   headers={"Authorization": f"Bearer {token}"},
                   json={"quantity": 3, "movement_type": "IN"})
        results.append(r.status_code)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start(); time.sleep(0.1); t2.start()
    t1.join(); t2.join()

    assert results.count(201) == 2
    with sqlserver_app.app_context():
        m = Material.query.get(mat_id)
        assert float(m.current_stock) == 16.0


# test_rollback_on_failure: valida el escenario rollback on failure preparando datos, ejecutando la accion y comprobando el resultado esperado.
@pytest.mark.sqlserver
def test_rollback_on_failure(sqlserver_client, sqlserver_app):
    admin_id, mat_id = _seed(sqlserver_app)
    token = _login(sqlserver_client, "admin", "Admin123!")
    # attempt OUT more than stock
    r = sqlserver_client.post(f"/api/v1/materials/{mat_id}/movements",
                              headers={"Authorization": f"Bearer {token}"},
                              json={"quantity": 100, "movement_type": "OUT"})
    assert r.status_code == 409
    with sqlserver_app.app_context():
        m = Material.query.get(mat_id)
        assert float(m.current_stock) == 10.0
        moves = StockMovement.query.filter_by(material_id=mat_id, movement_type="OUT").count()
        assert moves == 0


# test_history_integrity: valida el escenario history integrity preparando datos, ejecutando la accion y comprobando el resultado esperado.
@pytest.mark.sqlserver
def test_history_integrity(sqlserver_client, sqlserver_app):
    admin_id, mat_id = _seed(sqlserver_app)
    token = _login(sqlserver_client, "admin", "Admin123!")
    sqlserver_client.post(f"/api/v1/materials/{mat_id}/movements",
                         headers={"Authorization": f"Bearer {token}"},
                         json={"quantity": 2, "movement_type": "IN"})
    sqlserver_client.post(f"/api/v1/materials/{mat_id}/movements",
                         headers={"Authorization": f"Bearer {token}"},
                         json={"quantity": 1, "movement_type": "OUT"})
    with sqlserver_app.app_context():
        moves = StockMovement.query.filter_by(material_id=mat_id).count()
        m = Material.query.get(mat_id)
        assert moves == 2  # plus initial? none, stock set directly in _seed (no movement)
        assert float(m.current_stock) == 11.0
