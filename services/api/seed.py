"""Datos iniciales: roles, usuario administrador inicial y (opcional) catalogos. Idempotente.

Uso:
    python seed.py               roles + admin inicial (si aun no hay ningun usuario)
    python seed.py --catalogs    ademas carga catalogos base (paises/ciudades, especialidades, materiales)

Contrasena del admin inicial: ADMIN_PASSWORD o ADMIN_PASSWORD_FILE (nunca por argumentos). Debe cumplir la
politica de contrasenas; el usuario queda con must_change_password=True y debe cambiarla en el primer acceso.
Sin contrasena se genera una aleatoria que NO se muestra (habria que restablecerla): los instaladores siempre
la pasan. Si ya existe algun usuario no se crea ni se modifica nada (nunca restablece la contrasena).

Codigos de salida: 0 ok (creado o ya inicializado) | 2 contrasena invalida.
"""
import os
import sys

from app import create_app
from app.extensions import db
from app.identity.models import User, Role
from app.identity.passwords import generate_temporary_password, validate_password_policy

ROLES = [
    ("admin", "Administrador del sistema"),
    ("dispatcher", "Despachador de órdenes"),
    ("technician", "Técnico de campo"),
]
ADMIN_USERNAME = "admin"


def _admin_password():
    path = os.getenv("ADMIN_PASSWORD_FILE")
    if path:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    return os.getenv("ADMIN_PASSWORD") or None


def ensure_roles():
    """Crea los roles que falten (por nombre). Devuelve la cantidad creada."""
    existing = {r.name for r in Role.query.all()}
    missing = [Role(name=n, description=d) for n, d in ROLES if n not in existing]
    if missing:
        db.session.add_all(missing)
        db.session.commit()
    return len(missing)


def ensure_admin(password=None):
    """Crea el admin inicial solo si la base no tiene usuarios. Devuelve 'created' o 'exists'."""
    if User.query.count() > 0:
        return "exists"
    if password is None:
        password = generate_temporary_password(16)
    ok, msg = validate_password_policy(password, username=ADMIN_USERNAME)
    if not ok:
        raise ValueError(msg)
    admin = User(username=ADMIN_USERNAME, email="admin@sigos.local")
    admin.set_password(password)
    admin.roles = Role.query.filter_by(name="admin").all()
    admin.must_change_password = True
    db.session.add(admin)
    db.session.commit()
    return "created"


def seed_catalogs(app):
    """Catalogos base. Geografia/especialidades: solo inserta lo que falta. Materiales: solo si el catalogo
    esta vacio (load_into_app actualiza registros existentes y no debe pisar cambios hechos por el usuario)."""
    from app.materials.models import MaterialCatalog
    from seeds.seed_catalogs import seed as seed_base
    from seeds.load_catalog import load_into_app

    seed_base()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seeds", "materiales_gas_natural.json")
    if os.path.exists(path) and MaterialCatalog.query.count() == 0:
        load_into_app(app, path)


# Inserta datos iniciales en la base; interactua con la base de datos; escribe en consola.
def seed(catalogs=False):
    app = create_app()
    with app.app_context():
        if ensure_roles():
            print("Roles creados.")
        try:
            result = ensure_admin(_admin_password())
        except ValueError as exc:
            print(f"Contraseña del admin inicial no válida: {exc}", file=sys.stderr)
            return 2
        if result == "created":
            print("Usuario admin creado (username: admin). Debe cambiar la contraseña en el primer acceso.")
        else:
            print("Inicializacion ya realizada: la base ya tiene usuarios; no se crea ni modifica ninguno.")
        if catalogs:
            seed_catalogs(app)
            print("Catalogos base verificados.")
    return 0


if __name__ == "__main__":
    sys.exit(seed(catalogs="--catalogs" in sys.argv[1:]))
