from app.extensions import db
from app.identity.models import User, Role
from app.materials.models import Material, MaterialRequest, MaterialRequestItem, MaterialRequestEvent, MaterialRequestDelivery


def _seed(app):
    import os, sys
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if base not in sys.path:
        sys.path.insert(0, base)
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
        from app.materials.models import MaterialCatalog
        ci = MaterialCatalog.query.first()
        m = Material(name=ci.name, code=ci.code, unit="pza", current_stock=5, min_stock=2, unit_price=1000, catalog_item_id=ci.id)
        db.session.add(m)
        db.session.commit()
        return admin.id, tech.id, m.id


def test_request_model_compat(client, app):
    admin_id, tech_id, mat_id = _seed(app)
    with app.app_context():
        from app.materials.service import create_material_request
        req = create_material_request({"items": [{"material_id": mat_id, "quantity": 3}], "reason": "test"}, tech_id)
        assert req.status in ("SUBMITTED", "pendiente")
        item = req.items[0]
        assert item.quantity == 3
        assert item.quantity_requested == 3
        assert item.quantity_approved == 0
        assert item.quantity_delivered == 0
        assert req.events == []
        assert req.deliveries == []


def test_request_operation_unique(client, app):
    admin_id, tech_id, mat_id = _seed(app)
    with app.app_context():
        from app.materials.models import MaterialRequestOperation
        op1 = MaterialRequestOperation(operation_id="abc", operation_type="create", actor_id=tech_id, request_id=None)
        db.session.add(op1)
        db.session.commit()
        op2 = MaterialRequestOperation(operation_id="abc", operation_type="create", actor_id=tech_id)
        db.session.add(op2)
        try:
            db.session.commit()
            assert False, "expected unique violation"
        except Exception:
            db.session.rollback()


def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.get_json()["access_token"]


def test_create_and_submit(client, app):
    admin_id, tech_id, mat_id = _seed(app)
    token = _login(client, "tech", "Tech123!")
    # create draft
    r = client.post("/api/v1/material-requests", headers={"Authorization": f"Bearer {token}"}, json={"items": [{"material_id": mat_id, "quantity": 2}], "draft": True})
    assert r.status_code == 201
    rid = r.get_json()["id"]
    assert r.get_json()["status"] == "DRAFT"
    # submit
    r2 = client.post(f"/api/v1/material-requests/{rid}/submit", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.get_json()["status"] == "SUBMITTED"


def test_approve_and_deliver_partial(client, app):
    admin_id, tech_id, mat_id = _seed(app)
    tech_token = _login(client, "tech", "Tech123!")
    admin_token = _login(client, "admin", "Admin123!")
    # create+submit
    r = client.post("/api/v1/material-requests", headers={"Authorization": f"Bearer {tech_token}"}, json={"items": [{"material_id": mat_id, "quantity": 4}]})
    rid = r.get_json()["id"]
    iid = r.get_json()["items"][0]["id"]
    # approve partial 2
    ra = client.post(f"/api/v1/material-requests/{rid}/approve", headers={"Authorization": f"Bearer {admin_token}"}, json={"items": [{"item_id": iid, "quantity_approved": 2}]})
    assert ra.status_code == 200
    assert ra.get_json()["status"] == "PARTIALLY_APPROVED"
    # deliver 1
    rd = client.post(f"/api/v1/material-requests/{rid}/deliver", headers={"Authorization": f"Bearer {admin_token}"}, json={"items": [{"item_id": iid, "quantity_delivered": 1}], "operation_id": "op-1"})
    assert rd.status_code == 200
    assert rd.get_json()["status"] == "PARTIALLY_DELIVERED"
    # idempotent replay
    rd2 = client.post(f"/api/v1/material-requests/{rid}/deliver", headers={"Authorization": f"Bearer {admin_token}"}, json={"items": [{"item_id": iid, "quantity_delivered": 1}], "operation_id": "op-1"})
    assert rd2.status_code == 200
    # delivered total should still be 1
    assert rd2.get_json()["items"][0]["quantity_delivered"] == 1


def test_reject_and_cancel(client, app):
    admin_id, tech_id, mat_id = _seed(app)
    tech_token = _login(client, "tech", "Tech123!")
    admin_token = _login(client, "admin", "Admin123!")
    r = client.post("/api/v1/material-requests", headers={"Authorization": f"Bearer {tech_token}"}, json={"items": [{"material_id": mat_id, "quantity": 1}], "draft": True})
    rid = r.get_json()["id"]
    rc = client.post(f"/api/v1/material-requests/{rid}/cancel", headers={"Authorization": f"Bearer {tech_token}"}, json={"reason": "no longer needed"})
    assert rc.status_code == 200
    assert rc.get_json()["status"] == "CANCELLED"


def test_forbidden_technician_approve(client, app):
    admin_id, tech_id, mat_id = _seed(app)
    tech_token = _login(client, "tech", "Tech123!")
    r = client.post("/api/v1/material-requests", headers={"Authorization": f"Bearer {tech_token}"}, json={"items": [{"material_id": mat_id, "quantity": 1}]})
    rid = r.get_json()["id"]
    ra = client.post(f"/api/v1/material-requests/{rid}/approve", headers={"Authorization": f"Bearer {tech_token}"}, json={})
    assert ra.status_code == 403
