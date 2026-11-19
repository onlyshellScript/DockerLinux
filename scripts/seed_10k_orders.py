# Seed ~10000 work orders for load testing (RNF-01/RNF-02)
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))
from app import create_app
from app.config import Config
from app.extensions import db
from app.identity.models import User
from app.workorders.models import WorkOrder

app = create_app(Config)
with app.app_context():
    db.create_all()
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        from app.identity.models import Role
        r = Role(name="admin", description="Administrador")
        db.session.add(r)
        db.session.flush()
        admin = User(username="admin", email="admin@test.local")
        admin.set_password("Admin123!")
        admin.roles.append(r)
        db.session.add(admin)
        db.session.commit()
    for i in range(10000):
        db.session.add(WorkOrder(title=f"Load order {i}", created_by_id=admin.id, status="pending", priority="medium"))
        if i % 1000 == 0:
            db.session.commit()
    db.session.commit()
    print("seeded 10000 orders")
