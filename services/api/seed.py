"""Seed initial roles and admin user. Run once after migrations."""
from app import create_app
from app.extensions import db
from app.identity.models import User, Role


def seed():
    app = create_app()
    with app.app_context():
        if Role.query.count() == 0:
            db.session.add_all([
                Role(name="admin", description="Administrador del sistema"),
                Role(name="dispatcher", description="Despachador de órdenes"),
                Role(name="technician", description="Técnico de campo"),
            ])
            db.session.commit()
            print("Roles creados.")

        if User.query.count() == 0:
            admin = User(username="admin", email="admin@sigos.local")
            admin.set_password("Admin123!")
            admin.roles = Role.query.filter_by(name="admin").all()
            db.session.add(admin)
            db.session.commit()
            print("Usuario admin creado (username: admin, password: Admin123!).")


if __name__ == "__main__":
    seed()
