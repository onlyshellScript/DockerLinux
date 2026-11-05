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
