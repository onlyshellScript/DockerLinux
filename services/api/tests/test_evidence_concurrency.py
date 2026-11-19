# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.
import threading
import io

import pytest

from PIL import Image

from app.extensions import db
from app.identity.models import User, Role


# genera un PNG minimo de 1x1 en bytes para pruebas de carga de evidencia; sin parametros; salida bytes; sin efectos secundarios adicionales.
def _png():
    img = Image.new("RGB", (1, 1), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# test_concurrent_approve: valida el escenario concurrent approve preparando datos, ejecutando la accion y comprobando el resultado esperado.
@pytest.mark.sqlserver
def test_concurrent_approve(sqlserver_client, sqlserver_app):
    client = sqlserver_client
    app = sqlserver_app
    with app.app_context():
        admin_role = Role(name="admin", description="Administrador")
        tech_role = Role(name="technician", description="Tecnico")
        db.session.add_all([admin_role, tech_role])
        db.session.flush()
        admin1 = User(username="admin1", email="admin1@test.local")
        admin1.set_password("Admin123!")
        admin1.roles.append(admin_role)
        admin2 = User(username="admin2", email="admin2@test.local")
        admin2.set_password("Admin123!")
        admin2.roles.append(admin_role)
        tech = User(username="techc", email="techc@test.local")
        tech.set_password("Tech123!")
        tech.roles.append(tech_role)
        db.session.add_all([admin1, admin2, tech])
        db.session.commit()
        a1_id, a2_id, tech_id = admin1.id, admin2.id, tech.id

    def login(u, p):
        return client.post("/api/v1/auth/login", json={"username": u, "password": p}).get_json()["access_token"]

    atok1 = login("admin1", "Admin123!")
    atok2 = login("admin2", "Admin123!")
    ttok = login("techc", "Tech123!")

    # create work order assigned to tech via admin1
    wo = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {atok1}"},
        json={"title": "WO", "assigned_to_id": tech_id},
    ).get_json()["id"]

    # tech uploads evidence + refusal + submit
    buf = io.BytesIO(_png())
    client.post(
        f"/api/v1/work-orders/{wo}/evidences",
        headers={"Authorization": f"Bearer {ttok}"},
        data={"category": "BEFORE", "file": (buf, "p.png")},
        content_type="multipart/form-data",
    )
    client.post(
        f"/api/v1/work-orders/{wo}/signatures",
        headers={"Authorization": f"Bearer {ttok}"},
        json={"refused": True, "reason": "ausente"},
    )
    client.post(f"/api/v1/work-orders/{wo}/evidences/submit", headers={"Authorization": f"Bearer {ttok}"}, json={})
    client.post(f"/api/v1/work-orders/{wo}/evidences/start-review", headers={"Authorization": f"Bearer {atok1}"}, json={})

    results = []

    def approve(tok):
        r = client.post(f"/api/v1/work-orders/{wo}/evidences/approve", headers={"Authorization": f"Bearer {tok}"}, json={})
        results.append(r.status_code)

    t1 = threading.Thread(target=approve, args=(atok1,))
    t2 = threading.Thread(target=approve, args=(atok2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert all(code in (200,) for code in results)

    # events count: only one APPROVED event recorded
    from app.evidence.models import EvidenceEvent
    with app.app_context():
        evs = EvidenceEvent.query.filter_by(work_order_id=wo, action="APPROVED").count()
        assert evs == 1


# test_concurrent_approve_vs_correction: valida el escenario concurrent approve vs correction preparando datos, ejecutando la accion y comprobando el resultado esperado.
@pytest.mark.sqlserver
def test_concurrent_approve_vs_correction(sqlserver_client, sqlserver_app):
    client = sqlserver_client
    app = sqlserver_app
    with app.app_context():
        admin_role = Role(name="admin", description="Administrador")
        tech_role = Role(name="technician", description="Tecnico")
        db.session.add_all([admin_role, tech_role])
        db.session.flush()
        admin1 = User(username="adm1", email="adm1@test.local")
        admin1.set_password("Admin123!")
        admin1.roles.append(admin_role)
        admin2 = User(username="adm2", email="adm2@test.local")
        admin2.set_password("Admin123!")
        admin2.roles.append(admin_role)
        tech = User(username="techx", email="techx@test.local")
        tech.set_password("Tech123!")
        tech.roles.append(tech_role)
        db.session.add_all([admin1, admin2, tech])
        db.session.commit()
        a1, a2, t = admin1.id, admin2.id, tech.id

    def login(u, p):
        return client.post("/api/v1/auth/login", json={"username": u, "password": p}).get_json()["access_token"]

    atok1 = login("adm1", "Admin123!")
    atok2 = login("adm2", "Admin123!")
    ttok = login("techx", "Tech123!")

    wo = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {atok1}"}, json={"title": "WO", "assigned_to_id": t}).get_json()["id"]
    buf = io.BytesIO(_png())
    client.post(f"/api/v1/work-orders/{wo}/evidences", headers={"Authorization": f"Bearer {ttok}"}, data={"category": "BEFORE", "file": (buf, "p.png")}, content_type="multipart/form-data")
    client.post(f"/api/v1/work-orders/{wo}/signatures", headers={"Authorization": f"Bearer {ttok}"}, json={"refused": True, "reason": "ausente"})
    client.post(f"/api/v1/work-orders/{wo}/evidences/submit", headers={"Authorization": f"Bearer {ttok}"}, json={})
    client.post(f"/api/v1/work-orders/{wo}/evidences/start-review", headers={"Authorization": f"Bearer {atok1}"}, json={})

    results = []

    def approve():
        r = client.post(f"/api/v1/work-orders/{wo}/evidences/approve", headers={"Authorization": f"Bearer {atok1}"}, json={})
        results.append(("approve", r.status_code))

    def correct():
        r = client.post(f"/api/v1/work-orders/{wo}/evidences/request-correction", headers={"Authorization": f"Bearer {atok2}"}, json={"notes": "fix"})
        results.append(("correct", r.status_code))

    t1 = threading.Thread(target=approve)
    t2 = threading.Thread(target=correct)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    codes = sorted(code for _, code in results)
    # one success, one conflict
    assert 200 in codes
    assert 400 in codes