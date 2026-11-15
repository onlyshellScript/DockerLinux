
from app.extensions import db
from app.identity.models import User, Role


def _seed(app):
    with app.app_context():
        role = Role(name="admin", description="Administrador")
        db.session.add(role)
        db.session.flush()
        user = User(username="admin", email="admin@test.local")
        user.set_password("Admin123!")
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()
        return user.id


def test_rnf04_password_not_stored_plain(client, app):
    uid = _seed(app)
    with app.app_context():
        u = db.session.get(User, uid)
        assert u.password_hash != "Admin123!"
        assert u.password_hash.startswith("scrypt:") or "$" in u.password_hash


def test_rnf04_lockout_after_n_failures(client, app):
    _seed(app)
    for _ in range(5):
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert resp.status_code in (401, 429)
    from app.identity import service as _svc
    _svc._login_attempts.clear()


def test_app_does_not_start_without_jwt_secret_in_production(client, app):
    import os
    os.environ.pop("JWT_SECRET_KEY", None)
    os.environ.setdefault("DB_URL", "sqlite:///:memory:")
    started = False
    try:
        from app.config_prod import ProductionConfig
        from app import create_app
        create_app(ProductionConfig)
        started = True
    except (RuntimeError, KeyError):
        started = False
    assert started is False
    uid = _seed(app)
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
    token = resp.get_json()["access_token"]
    with app.app_context():
        u = db.session.get(User, uid)
        u.is_active = False
        db.session.commit()
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in (401, 403)


def test_rnf04_deactivated_user_token_rejected_all_roles(client, app):
    from app.identity.models import User, Role
    with app.app_context():
        for name in ("admin", "dispatcher", "technician"):
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name, description=name))
        db.session.flush()
        for name in ("admin", "dispatcher", "technician"):
            if not User.query.filter_by(username=name).first():
                u = User(username=name, email=f"{name}@test.local")
                u.set_password("Pass123!")
                u.roles.append(Role.query.filter_by(name=name).first())
                db.session.add(u)
        db.session.commit()
    for name in ("admin", "dispatcher", "technician"):
        resp = client.post("/api/v1/auth/login", json={"username": name, "password": "Pass123!"})
        token = resp.get_json()["access_token"]
        with app.app_context():
            u = User.query.filter_by(username=name).first()
            u.is_active = False
            db.session.commit()
        resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (401, 403)
