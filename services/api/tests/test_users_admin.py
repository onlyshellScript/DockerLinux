# Pruebas del modulo de administracion de usuarios: CRUD, validaciones, protecciones de administradores,
# restablecimiento de contrasena, autorizacion y auditoria.
import json

from app.extensions import db
from app.identity.models import AuditEvent, Role, User

ADMIN_PW = "Admin12345!"


def _seed(app):
    with app.app_context():
        roles = {n: Role(name=n, description=n) for n in ("admin", "dispatcher", "technician")}
        db.session.add_all(roles.values())
        admin = User(username="admin", email="admin@test.local")
        admin.set_password(ADMIN_PW)
        admin.roles.append(roles["admin"])
        disp = User(username="coord", email="coord@test.local")
        disp.set_password("Coord12345!")
        disp.roles.append(roles["dispatcher"])
        db.session.add_all([admin, disp])
        db.session.commit()
        return admin.id, disp.id


def _login(client, username="admin", password=ADMIN_PW):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.get_json()
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _create(client, h, **over):
    body = {"username": "nuevo", "email": "nuevo@test.local", "role_names": ["dispatcher"]}
    body.update(over)
    return client.post("/api/v1/users", headers=h, json=body)


def test_create_with_temporary_password_persists_and_audits(client, app):
    admin_id, _ = _seed(app)
    h = _login(client)
    r = _create(client, h)
    assert r.status_code == 201
    data = r.get_json()
    temp = data["temporary_password"]
    assert data["must_change_password"] is True and data["created_at"]
    with app.app_context():
        u = User.query.filter_by(username="nuevo").one()
        assert u.password_hash != temp and u.check_password(temp)
        assert [x.name for x in u.roles] == ["dispatcher"]
        ev = AuditEvent.query.filter_by(target_user_id=u.id, action="user_created").one()
        assert ev.actor_id == admin_id and temp not in (ev.changes or "")
    # El usuario nuevo entra pero debe cambiar la contrasena antes de usar la API.
    hn = _login(client, "nuevo", temp)
    assert client.get("/api/v1/work-orders", headers=hn).status_code == 403


def test_create_with_explicit_password_enforces_policy(client, app):
    _seed(app)
    h = _login(client)
    assert _create(client, h, password="corta").status_code == 422
    r = _create(client, h, password="Valida12345!")
    assert r.status_code == 201 and "temporary_password" not in r.get_json()


def test_create_validations(client, app):
    _seed(app)
    h = _login(client)
    assert _create(client, h, email="no-es-correo").get_json()["code"] == "invalid_email"
    assert _create(client, h, username="a").get_json()["code"] == "invalid_username"
    assert _create(client, h, role_names=[]).get_json()["code"] == "role_required"
    assert _create(client, h, role_names=["superadmin"]).get_json()["code"] == "invalid_role"


def test_duplicate_username_and_email_case_insensitive(client, app):
    _seed(app)
    h = _login(client)
    r = _create(client, h, username="otro", email="ADMIN@test.local")
    assert r.status_code == 409 and r.get_json()["code"] == "duplicate_email"
    r = _create(client, h, username="COORD", email="x@test.local")
    assert r.status_code == 409 and r.get_json()["code"] == "duplicate_username"


def test_edit_username_email_role_and_audit(client, app):
    admin_id, disp_id = _seed(app)
    h = _login(client)
    r = client.put(f"/api/v1/users/{disp_id}", headers=h, json={"username": "coord2", "email": "c2@test.local", "role_names": ["technician"]})
    assert r.status_code == 200
    with app.app_context():
        u = db.session.get(User, disp_id)
        assert (u.username, u.email, [x.name for x in u.roles]) == ("coord2", "c2@test.local", ["technician"])
        ev = AuditEvent.query.filter_by(target_user_id=disp_id, action="user_updated").one()
        assert ev.actor_id == admin_id and json.loads(ev.changes)["roles"] == [["dispatcher"], ["technician"]]
    # Editar con el correo de otro usuario se rechaza.
    r = client.put(f"/api/v1/users/{disp_id}", headers=h, json={"email": "admin@test.local"})
    assert r.status_code == 409 and r.get_json()["code"] == "duplicate_email"
    # La contrasena no se cambia por PUT.
    assert client.put(f"/api/v1/users/{disp_id}", headers=h, json={"password": "Otra12345!!"}).status_code == 422


def test_deactivate_blocks_login_and_keeps_record(client, app):
    _, disp_id = _seed(app)
    h = _login(client)
    hd = _login(client, "coord", "Coord12345!")
    assert client.put(f"/api/v1/users/{disp_id}", headers=h, json={"is_active": False}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"username": "coord", "password": "Coord12345!"}).status_code == 401
    assert client.get("/api/v1/work-orders", headers=hd).status_code == 401  # sesion abierta invalidada
    with app.app_context():
        assert db.session.get(User, disp_id) is not None
    assert client.put(f"/api/v1/users/{disp_id}", headers=h, json={"is_active": True}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"username": "coord", "password": "Coord12345!"}).status_code == 200


def test_admin_cannot_deactivate_or_demote_self(client, app):
    admin_id, _ = _seed(app)
    h = _login(client)
    r = client.put(f"/api/v1/users/{admin_id}", headers=h, json={"is_active": False})
    assert r.status_code == 409 and r.get_json()["code"] == "self_deactivation"
    r = client.put(f"/api/v1/users/{admin_id}", headers=h, json={"role_names": ["dispatcher"]})
    assert r.status_code == 409 and r.get_json()["code"] == "self_demotion"
    with app.app_context():
        u = db.session.get(User, admin_id)
        assert u.is_active and [x.name for x in u.roles] == ["admin"]


def test_last_active_admin_is_protected(client, app):
    admin_id, _ = _seed(app)
    h = _login(client)
    r = _create(client, h, username="admin2", email="admin2@test.local", role_names=["admin"], password="Admin2_12345")
    admin2_id = r.get_json()["id"]
    h2 = _login(client, "admin2", "Admin2_12345")
    # Con dos admins, admin2 puede desactivar al primero; luego el primero ya no puede ser el ultimo en caer.
    assert client.put(f"/api/v1/users/{admin_id}", headers=h2, json={"is_active": False}).status_code == 200
    with app.app_context():
        from app.identity.service import update_user, UserAdminError
        try:
            update_user(admin2_id, {"is_active": False}, actor_id=None)
            raise AssertionError("debio rechazarse")
        except UserAdminError as exc:
            assert exc.code == "last_admin"


def test_reset_password_once_and_forces_change(client, app):
    admin_id, disp_id = _seed(app)
    h = _login(client)
    hd = _login(client, "coord", "Coord12345!")
    r = client.post(f"/api/v1/users/{disp_id}/reset-password", headers=h)
    assert r.status_code == 200 and "no-store" in r.headers.get("Cache-Control", "")
    temp = r.get_json()["temporary_password"]
    # La contrasena anterior deja de servir y la sesion abierta queda revocada en el servidor.
    assert client.post("/api/v1/auth/login", json={"username": "coord", "password": "Coord12345!"}).status_code == 401
    assert client.get("/api/v1/work-orders", headers=hd).status_code == 401
    hn = _login(client, "coord", temp)
    assert client.post("/api/v1/auth/change-password", headers=hn, json={"current_password": temp, "new_password": "Nueva12345!"}).status_code == 200
    # La contrasena temporal no puede reutilizarse ni consultarse despues.
    assert client.post("/api/v1/auth/login", json={"username": "coord", "password": temp}).status_code == 401
    assert "temporary_password" not in client.get(f"/api/v1/users/{disp_id}", headers=h).get_json()
    with app.app_context():
        ev = AuditEvent.query.filter_by(target_user_id=disp_id, action="password_reset").one()
        assert ev.actor_id == admin_id and temp not in (ev.changes or "")
    assert client.post(f"/api/v1/users/{admin_id}/reset-password", headers=h).get_json()["code"] == "self_reset"


def test_non_admin_cannot_manage_users(client, app):
    admin_id, disp_id = _seed(app)
    hd = _login(client, "coord", "Coord12345!")
    assert client.get("/api/v1/users", headers=hd).status_code == 403
    assert _create(client, hd, role_names=["admin"]).status_code == 403
    assert client.put(f"/api/v1/users/{disp_id}", headers=hd, json={"role_names": ["admin"]}).status_code == 403
    assert client.post(f"/api/v1/users/{admin_id}/reset-password", headers=hd).status_code == 403


def test_role_removal_applies_immediately(client, app):
    _seed(app)
    h = _login(client)
    r = _create(client, h, username="admin2", email="admin2@test.local", role_names=["admin"], password="Admin2_12345")
    h2 = _login(client, "admin2", "Admin2_12345")
    assert client.get("/api/v1/users", headers=h2).status_code == 200
    assert client.put(f"/api/v1/users/{r.get_json()['id']}", headers=h, json={"role_names": ["dispatcher"]}).status_code == 200
    # El token de admin2 aun dice "admin", pero el rol se valida contra la base.
    assert client.get("/api/v1/users", headers=h2).status_code == 403


def test_list_filters(client, app):
    _seed(app)
    h = _login(client)
    _create(client, h, username="inactivo", email="ina@test.local", is_active=False)
    names = lambda qs: sorted(u["username"] for u in client.get("/api/v1/users" + qs, headers=h).get_json())
    assert names("?role=admin") == ["admin"]
    assert names("?status=inactive") == ["inactivo"]
    assert names("?q=COORD") == ["coord"]
    assert client.get("/api/v1/users?status=raro", headers=h).status_code == 400
    assert sorted(r["name"] for r in client.get("/api/v1/roles", headers=h).get_json()) == ["admin", "dispatcher", "technician"]


def test_role_removal_applies_to_routes_with_manual_role_checks(client, app):
    # require_auth + comprobacion manual de request.user_roles (p. ej. /settings/organization)
    _seed(app)
    h = _login(client)
    r = _create(client, h, username="admin2", email="admin2@test.local", role_names=["admin"], password="Admin2_12345")
    h2 = _login(client, "admin2", "Admin2_12345")
    assert client.get("/api/v1/settings/organization", headers=h2).status_code == 200
    assert client.put(f"/api/v1/users/{r.get_json()['id']}", headers=h, json={"role_names": ["technician"]}).status_code == 200
    # El token de admin2 aun dice "admin"; los roles se leen de la base.
    assert client.get("/api/v1/settings/organization", headers=h2).status_code == 403
