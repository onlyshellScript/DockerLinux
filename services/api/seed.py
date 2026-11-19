"""Seed initial roles and admin user. Run once after migrations."""
import os
import secrets

from app import create_app
from app.extensions import db
from app.identity.models import User, Role


# Inserta datos iniciales en la base; recibe sin parametros; interactua con la base de datos; accede al sistema de archivos; escribe en consola; devuelve el valor correspondiente.
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
            admin.set_password(os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(16))
            admin.roles = Role.query.filter_by(name="admin").all()

            admin.must_change_password = True
            db.session.add(admin)
            db.session.commit()
            print("Usuario admin creado (username: admin). Configure ADMIN_PASSWORD para una contraseña conocida; la inicial es aleatoria y debe cambiarse en el primer acceso.")


if __name__ == "__main__":
    seed()
