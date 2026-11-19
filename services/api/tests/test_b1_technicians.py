# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.
import os

import pytest

from app.identity.models import User, Role
from app.extensions import db

# Inserta datos iniciales en la base; recibe app; interactua con la base de datos; devuelve el valor correspondiente.

def _seed_roles(app):
    with app.app_context():
        for name, desc in [("admin", "Administrador"), ("dispatcher", "Despachador"), ("technician", "Tecnico")]:
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name, description=desc))
        db.session.commit()
        if not User.query.filter_by(username="admin").first():
            u = User(username="admin", email="admin@test.local")
            u.set_password("Admin123!")
            u.roles.append(Role.query.filter_by(name="admin").first())
            db.session.add(u)
            db.session.commit()


# _token: realiza login y devuelve el access_token para el usuario indicado; entradas client, username, password; salida str; efecto secundario autentica.
def _token(client, username, password):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    return r.get_json()["access_token"]


# admin_token: fixture de pytest que crea roles y devuelve un token de admin.
@pytest.fixture
def admin_token(client, app):
    _seed_roles(app)
    return _token(client, "admin", "Admin123!")

# test_b1_create_requires_fields: valida el escenario b1 create requires fields preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_create_requires_fields(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    r = client.post("/api/v1/technicians", json={"first_name": "Juan"}, headers=headers)
    assert r.status_code == 422

# test_b1_create_requires_document: valida el escenario b1 create requires document preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_create_requires_document(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    r = client.post("/api/v1/technicians", json={"first_name": "Juan", "last_name": "Perez"}, headers=headers)
    assert r.status_code == 422

# test_b1_create_invalid_doc_type: valida el escenario b1 create invalid doc type preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_create_invalid_doc_type(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    r = client.post("/api/v1/technicians", json={"first_name": "Juan", "last_name": "Perez", "document_type": "XX", "document_number": "123"}, headers=headers)
    assert r.status_code == 422

# test_b1_create_missing_initial_password: valida el escenario b1 create missing initial password preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_create_missing_initial_password(client, app, admin_token):
    os.environ.pop("TECH_INITIAL_PASSWORD", None)
    headers = {"Authorization": "Bearer " + admin_token}
    r = client.post("/api/v1/technicians", json={"first_name": "Juan", "last_name": "Perez", "document_type": "CC", "document_number": "999"}, headers=headers)
    assert r.status_code == 500

# test_b1_create_success: valida el escenario b1 create success preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_create_success(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    r = client.post("/api/v1/technicians", json={"first_name": "Juan", "last_name": "Perez", "document_type": "CC", "document_number": "1001", "specialty": None}, headers=headers)
    assert r.status_code == 201
    data = r.get_json()
    assert "temporary_password" not in data
    assert data["username"]
    # must_change_password true in db
    with app.app_context():
        from app.materials.models import TechnicianProfile
        prof = TechnicianProfile.query.filter_by(document_number="1001").first()
        assert prof is not None
        assert prof.user.must_change_password is True

# test_b1_document_unique: valida el escenario b1 document unique preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_document_unique(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    client.post("/api/v1/technicians", json={"first_name": "A", "last_name": "B", "document_type": "CC", "document_number": "2002"}, headers=headers)
    r = client.post("/api/v1/technicians", json={"first_name": "C", "last_name": "D", "document_type": "CC", "document_number": "2002"}, headers=headers)
    assert r.status_code == 409

# test_b1_department_municipality_validation: valida el escenario b1 department municipality validation preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_department_municipality_validation(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    r = client.post("/api/v1/technicians", json={"first_name": "X", "last_name": "Y", "document_type": "CC", "document_number": "3003", "department_code": "XX", "municipality_code": "00000"}, headers=headers)
    assert r.status_code == 422
    from app.catalogs.models import Department, Municipality
    with app.app_context():
        dep = Department.query.first()
        if not dep:
            return
        mun = Municipality.query.filter(Municipality.department_code != dep.code).first()
        if mun:
            r2 = client.post("/api/v1/technicians", json={"first_name": "X2", "last_name": "Y2", "document_type": "CC", "document_number": "3004", "department_code": dep.code, "municipality_code": mun.code}, headers=headers)
            assert r2.status_code == 422

# test_b1_patch_username_unique: valida el escenario b1 patch username unique preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_patch_username_unique(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    r = client.post("/api/v1/technicians", json={"first_name": "U1", "last_name": "V1", "document_type": "CC", "document_number": "4004"}, headers=headers)
    tid = r.get_json()["technician"]["id"]
    # rename to existing admin username
    r2 = client.patch("/api/v1/technicians/{}".format(tid), json={"username": "admin"}, headers=headers)
    assert r2.status_code == 409

# test_b1_patch_password_rejected: valida el escenario b1 patch password rejected preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_patch_password_rejected(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    r = client.post("/api/v1/technicians", json={"first_name": "P1", "last_name": "Q1", "document_type": "CC", "document_number": "5005"}, headers=headers)
    tid = r.get_json()["technician"]["id"]
    r2 = client.patch("/api/v1/technicians/{}".format(tid), json={"password": "NewPass123!"}, headers=headers)
    assert r2.status_code == 422

# test_b1_dispatcher_cannot_create: valida el escenario b1 dispatcher cannot create preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_dispatcher_cannot_create(client, app):
    _seed_roles(app)
    # ensure dispatcher user exists
    with app.app_context():
        if not User.query.filter_by(username="dispatcher").first():
            u = User(username="dispatcher", email="dispatcher@test.local")
            u.set_password("Disp123!")
            u.roles.append(Role.query.filter_by(name="dispatcher").first())
            db.session.add(u)
            db.session.commit()
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    disp_tok = _token(client, "dispatcher", "Disp123!")
    headers = {"Authorization": "Bearer " + disp_tok}
    r = client.post("/api/v1/technicians", json={"first_name": "D", "last_name": "P", "document_type": "CC", "document_number": "7007"}, headers=headers)
    assert r.status_code in (401, 403)

# test_b1_initial_password_stored_hashed: valida el escenario b1 initial password stored hashed preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_initial_password_stored_hashed(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    r = client.post("/api/v1/technicians", json={"first_name": "H1", "last_name": "H2", "document_type": "CC", "document_number": "9001"}, headers=headers)
    assert r.status_code == 201
    with app.app_context():
        from app.materials.models import TechnicianProfile
        prof = TechnicianProfile.query.filter_by(document_number="9001").first()
        assert prof is not None
        u = prof.user
        assert u.password_hash != "InitPass123!"
        assert u.check_password("InitPass123!") is True
        assert u.must_change_password is True

# test_b1_password_not_in_create_list_edit_responses: valida el escenario b1 password not in create list edit responses preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_password_not_in_create_list_edit_responses(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    r = client.post("/api/v1/technicians", json={"first_name": "N1", "last_name": "N2", "document_type": "CC", "document_number": "9002"}, headers=headers)
    assert r.status_code == 201
    body = r.get_data(as_text=True)
    assert "InitPass123!" not in body
    tid = r.get_json()["technician"]["id"]
    rl = client.get("/api/v1/technicians", headers=headers)
    assert "InitPass123!" not in rl.get_data(as_text=True)
    rp = client.patch("/api/v1/technicians/{}".format(tid), json={"phone": "555"}, headers=headers)
    assert rp.status_code == 200
    assert "InitPass123!" not in rp.get_data(as_text=True)

# test_b1_second_names_concatenated: valida el escenario b1 second names concatenated preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_second_names_concatenated(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    r = client.post("/api/v1/technicians", json={"first_name": "Juan", "second_name": "Carlos", "last_name": "Perez", "second_last_name": "Gomez", "document_type": "CC", "document_number": "9003"}, headers=headers)
    assert r.status_code == 201
    tech = r.get_json()["technician"]
    assert tech["first_name"] == "Juan Carlos"
    assert tech["last_name"] == "Perez Gomez"
    tid = tech["id"]
    rp = client.patch("/api/v1/technicians/{}".format(tid), json={"first_name": "Ana", "second_name": "Maria", "last_name": "Lopez"}, headers=headers)
    assert rp.status_code == 200
    assert rp.get_json()["first_name"] == "Ana Maria"

# test_b1_technician_own_profile_only: valida el escenario b1 technician own profile only preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_b1_technician_own_profile_only(client, app, admin_token):
    os.environ["TECH_INITIAL_PASSWORD"] = "InitPass123!"
    headers = {"Authorization": "Bearer " + admin_token}
    r1 = client.post("/api/v1/technicians", json={"first_name": "T1", "last_name": "U1", "document_type": "CC", "document_number": "9101"}, headers=headers)
    assert r1.status_code == 201
    tid1 = r1.get_json()["technician"]["id"]
    username1 = r1.get_json()["username"]
    r2 = client.post("/api/v1/technicians", json={"first_name": "T2", "last_name": "U2", "document_type": "CC", "document_number": "9102"}, headers=headers)
    assert r2.status_code == 201
    tid2 = r2.get_json()["technician"]["id"]
    tok1 = _token(client, username1, "InitPass123!")
    h1 = {"Authorization": "Bearer " + tok1}
    assert client.get("/api/v1/technicians/{}".format(tid1), headers=h1).status_code == 200
    assert client.get("/api/v1/technicians/{}".format(tid2), headers=h1).status_code == 403
