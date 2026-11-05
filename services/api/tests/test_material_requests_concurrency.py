import os, sys, threading, time

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base not in sys.path:
    sys.path.insert(0, base)

import pytest

from app.extensions import db
from app.identity.models import User, Role
from app.materials.models import Material, MaterialCatalog, MaterialRequest, MaterialRequestItem, StockMovement, TechnicianStock, MaterialRequestDelivery


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
        from seeds.load_catalog import load_into_app
        load_into_app(app, os.path.join(base, "seeds", "materiales_gas_natural.json"))
        ci = MaterialCatalog.query.first()
        m = Material(name=ci.name, code=ci.code, unit="pza", current_stock=10, min_stock=2, unit_price=1000, catalog_item_id=ci.id)
        db.session.add(m)
        db.session.commit()
        # technician profile
        from app.materials.models import TechnicianProfile
        prof = TechnicianProfile(user_id=tech.id, is_available=True)
        db.session.add(prof)
        db.session.commit()
        return admin.id, tech.id, tech.id, m.id, prof.id


def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]


@pytest.mark.sqlserver
def test_concurrent_deliveries_same_item(sqlserver_client, sqlserver_app):
    admin_id, tech_user_id, tech_id_unused, mat_id, prof_id = _seed(sqlserver_app)
    tech_token = _login(sqlserver_client, "tech", "Tech123!")
    admin_token = _login(sqlserver_client, "admin", "Admin123!")
    # create request by tech
    r = sqlserver_client.post("/api/v1/material-requests", headers={"Authorization": f"Bearer {tech_token}"}, json={"items": [{"material_id": mat_id, "quantity": 4}], "technician_id": prof_id})
    rid = r.get_json()["id"]
    iid = r.get_json()["items"][0]["id"]
    # approve 4
    sqlserver_client.post(f"/api/v1/material-requests/{rid}/approve", headers={"Authorization": f"Bearer {admin_token}"}, json={"items": [{"item_id": iid, "quantity_approved": 4}]})
    results = []

    def worker(opid):
        c = sqlserver_app.test_client()
        r = c.post(f"/api/v1/material-requests/{rid}/deliver", headers={"Authorization": f"Bearer {admin_token}"}, json={"items": [{"item_id": iid, "quantity_delivered": 3}], "operation_id": opid})
        results.append(r.status_code)

    t1 = threading.Thread(target=worker, args=("op-a",))
    t2 = threading.Thread(target=worker, args=("op-b",))
    t1.start(); time.sleep(0.1); t2.start()
    t1.join(); t2.join()

    with sqlserver_app.app_context():
        req = MaterialRequest.query.get(rid)
        item = req.items[0]
        # only one delivery of 2 should succeed (total delivered 2, not 4)
        assert item.quantity_delivered == 3.0
        dels = MaterialRequestDelivery.query.filter_by(request_id=rid).count()
        assert dels == 1
    # one 200, one 409
    assert sorted(results) == [200, 409] or sorted(results) == [409, 200]


@pytest.mark.sqlserver
def test_idempotent_replay(sqlserver_client, sqlserver_app):
    admin_id, tech_user_id, tech_id_unused, mat_id, prof_id = _seed(sqlserver_app)
    tech_token = _login(sqlserver_client, "tech", "Tech123!")
    admin_token = _login(sqlserver_client, "admin", "Admin123!")
    r = sqlserver_client.post("/api/v1/material-requests", headers={"Authorization": f"Bearer {tech_token}"}, json={"items": [{"material_id": mat_id, "quantity": 2}], "technician_id": prof_id})
    rid = r.get_json()["id"]
    iid = r.get_json()["items"][0]["id"]
    sqlserver_client.post(f"/api/v1/material-requests/{rid}/approve", headers={"Authorization": f"Bearer {admin_token}"}, json={"items": [{"item_id": iid, "quantity_approved": 2}]})
    r1 = sqlserver_client.post(f"/api/v1/material-requests/{rid}/deliver", headers={"Authorization": f"Bearer {admin_token}"}, json={"items": [{"item_id": iid, "quantity_delivered": 2}], "operation_id": "op-idem"})
    r2 = sqlserver_client.post(f"/api/v1/material-requests/{rid}/deliver", headers={"Authorization": f"Bearer {admin_token}"}, json={"items": [{"item_id": iid, "quantity_delivered": 2}], "operation_id": "op-idem"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    with sqlserver_app.app_context():
        item = MaterialRequestItem.query.get(iid)
        assert item.quantity_delivered == 2.0
        dels = MaterialRequestDelivery.query.filter_by(request_id=rid).count()
        assert dels == 1


@pytest.mark.sqlserver
def test_exceeds_approved(sqlserver_client, sqlserver_app):
    admin_id, tech_user_id, tech_id_unused, mat_id, prof_id = _seed(sqlserver_app)
    tech_token = _login(sqlserver_client, "tech", "Tech123!")
    admin_token = _login(sqlserver_client, "admin", "Admin123!")
    r = sqlserver_client.post("/api/v1/material-requests", headers={"Authorization": f"Bearer {tech_token}"}, json={"items": [{"material_id": mat_id, "quantity": 2}], "technician_id": prof_id})
    rid = r.get_json()["id"]
    iid = r.get_json()["items"][0]["id"]
    sqlserver_client.post(f"/api/v1/material-requests/{rid}/approve", headers={"Authorization": f"Bearer {admin_token}"}, json={"items": [{"item_id": iid, "quantity_approved": 1}]})
    r2 = sqlserver_client.post(f"/api/v1/material-requests/{rid}/deliver", headers={"Authorization": f"Bearer {admin_token}"}, json={"items": [{"item_id": iid, "quantity_delivered": 2}]})
    assert r2.status_code == 409
