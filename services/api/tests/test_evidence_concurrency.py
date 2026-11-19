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


# firma de prueba del tecnico (trazo sobre lienzo transparente) como data URL.
def _signature_data_url():
    import base64
    from PIL import ImageDraw
    img = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
    ImageDraw.Draw(img).line([(20, 70), (120, 20), (280, 60)], fill=(20, 20, 20, 255), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# test_concurrent_approve: valida el escenario concurrent approve preparando datos, ejecutando la accion y comprobando el resultado esperado.
@pytest.mark.sqlserver
def test_concurrent_approve(sqlserver_client, sqlserver_app):
    client = sqlserver_client
    app = sqlserver_app
    with app.app_context():
        admin_role = Role(name="admin", description="Administrador")
        tech_role = Role(name="technician", description="Tecnico")
        disp_role = Role(name="dispatcher", description="Despachador")
        db.session.add_all([admin_role, tech_role, disp_role])
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
        disp = User(username="dispc", email="dispc@test.local")
        disp.set_password("Disp123!")
        disp.roles.append(disp_role)
        db.session.add_all([admin1, admin2, tech, disp])
        db.session.commit()
        a1_id, a2_id, tech_id = admin1.id, admin2.id, tech.id

    def login(u, p):
        return client.post("/api/v1/auth/login", json={"username": u, "password": p}).get_json()["access_token"]

    atok1 = login("admin1", "Admin123!")
    atok2 = login("admin2", "Admin123!")
    ttok = login("techc", "Tech123!")
    dtok = login("dispc", "Disp123!")
    assert client.post("/api/v1/me/signature", headers={"Authorization": f"Bearer {ttok}"},
                       json={"image": _signature_data_url()}).status_code == 201

    # create work order assigned to tech via dispatcher (solo dispatcher crea ordenes)
    wo = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {dtok}"},
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

    # Libera la sesion del contexto del fixture: las peticiones del hilo principal la reutilizan y su
    # transaccion abierta bloquearia en SQL Server a los hilos concurrentes.
    db.session.remove()

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
        disp_role = Role(name="dispatcher", description="Despachador")
        db.session.add_all([admin_role, tech_role, disp_role])
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
        disp = User(username="dispx", email="dispx@test.local")
        disp.set_password("Disp123!")
        disp.roles.append(disp_role)
        db.session.add_all([admin1, admin2, tech, disp])
        db.session.commit()
        a1, a2, t = admin1.id, admin2.id, tech.id

    def login(u, p):
        return client.post("/api/v1/auth/login", json={"username": u, "password": p}).get_json()["access_token"]

    atok1 = login("adm1", "Admin123!")
    atok2 = login("adm2", "Admin123!")
    ttok = login("techx", "Tech123!")
    dtok = login("dispx", "Disp123!")
    assert client.post("/api/v1/me/signature", headers={"Authorization": f"Bearer {ttok}"},
                       json={"image": _signature_data_url()}).status_code == 201

    wo = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {dtok}"}, json={"title": "WO", "assigned_to_id": t}).get_json()["id"]
    buf = io.BytesIO(_png())
    client.post(f"/api/v1/work-orders/{wo}/evidences", headers={"Authorization": f"Bearer {ttok}"}, data={"category": "BEFORE", "file": (buf, "p.png")}, content_type="multipart/form-data")
    client.post(f"/api/v1/work-orders/{wo}/signatures", headers={"Authorization": f"Bearer {ttok}"}, json={"refused": True, "reason": "ausente"})
    client.post(f"/api/v1/work-orders/{wo}/evidences/submit", headers={"Authorization": f"Bearer {ttok}"}, json={})
    client.post(f"/api/v1/work-orders/{wo}/evidences/start-review", headers={"Authorization": f"Bearer {atok1}"}, json={})

    # Libera la sesion del contexto del fixture: las peticiones del hilo principal la reutilizan y su
    # transaccion abierta bloquearia en SQL Server a los hilos concurrentes.
    db.session.remove()

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
    # una operacion gana y la otra se rechaza por conflicto de estado
    assert codes.count(200) == 1, codes
    assert codes[1] in (400, 409), codes