# Inicializacion del admin inicial (seed.py): idempotente, rol admin real, cambio obligatorio y politica.
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import seed as seed_mod  # noqa: E402
from app.extensions import db  # noqa: E402
from app.identity.models import User, Role  # noqa: E402


def test_crea_roles_y_admin_con_cambio_obligatorio(app):
    with app.app_context():
        assert seed_mod.ensure_roles() == 3
        assert seed_mod.ensure_admin("Inicial-2026-Xy") == "created"
        admin = User.query.filter_by(username="admin").one()
        assert [r.name for r in admin.roles] == ["admin"]
        assert admin.must_change_password is True
        assert admin.check_password("Inicial-2026-Xy")


def test_segunda_ejecucion_no_duplica_ni_restablece(app):
    with app.app_context():
        seed_mod.ensure_roles()
        seed_mod.ensure_admin("Inicial-2026-Xy")
        assert seed_mod.ensure_roles() == 0
        assert seed_mod.ensure_admin("Otra-Clave-2026") == "exists"
        assert User.query.count() == 1
        assert Role.query.count() == 3
        assert User.query.filter_by(username="admin").one().check_password("Inicial-2026-Xy")


def test_rechaza_contrasena_debil(app):
    with app.app_context():
        seed_mod.ensure_roles()
        with pytest.raises(ValueError):
            seed_mod.ensure_admin("corta")
        assert User.query.count() == 0


def test_sin_contrasena_genera_una_que_cumple_la_politica(app):
    with app.app_context():
        seed_mod.ensure_roles()
        assert seed_mod.ensure_admin(None) == "created"
        assert User.query.filter_by(username="admin").one().must_change_password is True


def test_login_admin_exige_cambio_de_contrasena(app, client):
    with app.app_context():
        seed_mod.ensure_roles()
        seed_mod.ensure_admin("Inicial-2026-Xy")
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Inicial-2026-Xy"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["user"]["must_change_password"] is True
    tok = body["access_token"]
    blocked = client.get("/api/v1/users", headers={"Authorization": f"Bearer {tok}"})
    assert blocked.status_code == 403
    ch = client.post("/api/v1/auth/change-password", headers={"Authorization": f"Bearer {tok}"},
                     json={"current_password": "Inicial-2026-Xy", "new_password": "Definitiva-2026-Ab"})
    assert ch.status_code == 200


def test_catalogos_idempotentes(app):
    with app.app_context():
        seed_mod.seed_catalogs(app)
        from app.catalogs.models import Specialty
        from app.materials.models import MaterialCatalog
        n_spec, n_mat = Specialty.query.count(), MaterialCatalog.query.count()
        seed_mod.seed_catalogs(app)
        assert Specialty.query.count() == n_spec > 0
        assert MaterialCatalog.query.count() == n_mat > 0
