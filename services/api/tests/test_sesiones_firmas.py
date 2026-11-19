# Pruebas de aislamiento de sesiones, firma del tecnico (perfil e historica inmutable) y listado de evidencias por orden.
import base64
import io
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from PIL import Image, ImageDraw

from app.extensions import db
from app.identity.models import User, Role, UserSession


def _png(size=(1, 1), color="white"):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _signature_png(seed=0):
    img = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
    ImageDraw.Draw(img).line([(20, 70), (120 + seed * 10, 20), (280, 60)], fill=(20, 20, 20, 255), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _data_url(png):
    return "data:image/png;base64," + base64.b64encode(png).decode()


def _seed(app):
    with app.app_context():
        roles = {n: Role(name=n, description=n) for n in ("admin", "dispatcher", "technician")}
        db.session.add_all(roles.values())
        db.session.flush()
        users = {}
        for name, role, pwd in [("admin", "admin", "Admin123!"), ("disp", "dispatcher", "Disp123!"),
                                ("tech", "technician", "Tech123!"), ("tech2", "technician", "Tech223!")]:
            u = User(username=name, email=f"{name}@test.local")
            u.set_password(pwd)
            u.roles.append(roles[role])
            db.session.add(u)
            users[name] = u
        db.session.commit()
        return {k: v.id for k, v in users.items()}


PASSWORDS = {"admin": "Admin123!", "disp": "Disp123!", "tech": "Tech123!", "tech2": "Tech223!"}


def _login(client, name):
    r = client.post("/api/v1/auth/login", json={"username": name, "password": PASSWORDS[name]})
    assert r.status_code == 200
    return r.get_json()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _wo(client, token, assigned_to_id=None, title="Orden de prueba"):
    payload = {"title": title}
    if assigned_to_id:
        payload["assigned_to_id"] = assigned_to_id
    r = client.post("/api/v1/work-orders", headers=_h(token), json=payload)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def _upload(client, token, wo_id, **extra):
    data = {"category": "BEFORE", "file": (io.BytesIO(_png()), "p.png")}
    data.update(extra)
    return client.post(f"/api/v1/work-orders/{wo_id}/evidences", headers=_h(token), data=data, content_type="multipart/form-data")


# ---------------- Aislamiento de sesiones ----------------

def test_logout_revoca_access_y_refresh_en_el_servidor(client, app):
    _seed(app)
    admin = _login(client, "admin")
    assert client.get("/api/v1/users", headers=_h(admin["access_token"])).status_code == 200
    r = client.post("/api/v1/auth/logout", headers=_h(admin["access_token"]), json={"refresh_token": admin["refresh_token"]})
    assert r.status_code == 200 and r.get_json()["revoked"] is True
    # Reutilizar una peticion de la sesion administrativa cerrada: el token aun no vence, pero ya no sirve.
    r = client.get("/api/v1/users", headers=_h(admin["access_token"]))
    assert r.status_code == 401 and r.get_json()["code"] == "session_revoked"
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": admin["refresh_token"]}).status_code == 401
    # El logout es idempotente.
    assert client.post("/api/v1/auth/logout", headers=_h(admin["access_token"])).status_code == 200


def test_tecnico_tras_logout_de_admin_no_accede_a_datos_administrativos(client, app):
    ids = _seed(app)
    admin = _login(client, "admin")
    disp = _login(client, "disp")
    own = _wo(client, disp["access_token"], ids["tech"], "Orden del tecnico")
    other = _wo(client, disp["access_token"], ids["tech2"], "Orden de otro tecnico")
    client.post("/api/v1/auth/logout", headers=_h(admin["access_token"]))

    tech = _login(client, "tech")
    th = _h(tech["access_token"])
    assert client.get("/api/v1/users", headers=th).status_code == 403
    assert client.get("/api/v1/evidences/inbox", headers=th).status_code == 403
    assert client.get(f"/api/v1/work-orders/{other}/evidences", headers=th).status_code == 403
    listing = client.get("/api/v1/evidences/orders", headers=th).get_json()
    assert [i["work_order"]["id"] for i in listing["items"]] == [own]
    # Pedir explicitamente las ordenes de otro tecnico no amplia el alcance.
    listing = client.get(f"/api/v1/evidences/orders?technician_id={ids['tech2']}", headers=th).get_json()
    assert [i["work_order"]["id"] for i in listing["items"]] == [own]


def test_logout_con_access_vencido_revoca_por_refresh(client, app):
    _seed(app)
    s = _login(client, "admin")
    with app.app_context():
        claims = jwt.decode(s["access_token"], "test-secret", algorithms=["HS256"])
        claims["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
        expired = jwt.encode(claims, "test-secret", algorithm="HS256")
    assert client.post("/api/v1/auth/logout", headers=_h(expired)).get_json()["revoked"] is True
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401


def test_token_sin_sesion_o_de_otra_sesion_se_rechaza(client, app):
    ids = _seed(app)
    s = _login(client, "tech")
    claims = jwt.decode(s["access_token"], "test-secret", algorithms=["HS256"])
    no_sid = dict(claims)
    no_sid.pop("sid")
    assert client.get("/api/v1/work-orders", headers=_h(jwt.encode(no_sid, "test-secret", algorithm="HS256"))).status_code == 401
    # Una sesion valida de otro usuario no autentica a este.
    admin = _login(client, "admin")
    admin_sid = jwt.decode(admin["access_token"], "test-secret", algorithms=["HS256"])["sid"]
    forged = dict(claims, sid=admin_sid)
    assert client.get("/api/v1/work-orders", headers=_h(jwt.encode(forged, "test-secret", algorithm="HS256"))).status_code == 401


def test_sesiones_independientes_y_desactivacion(client, app):
    ids = _seed(app)
    a = _login(client, "tech")
    b = _login(client, "tech")
    client.post("/api/v1/auth/logout", headers=_h(a["access_token"]))
    assert client.get("/api/v1/work-orders", headers=_h(a["access_token"])).status_code == 401
    assert client.get("/api/v1/work-orders", headers=_h(b["access_token"])).status_code == 200
    admin = _login(client, "admin")
    assert client.put(f"/api/v1/users/{ids['tech']}", headers=_h(admin["access_token"]), json={"is_active": False}).status_code == 200
    with app.app_context():
        assert UserSession.query.filter_by(user_id=ids["tech"], revoked_at=None).count() == 0


def test_respuestas_api_no_se_guardan_en_cache(client, app):
    _seed(app)
    s = _login(client, "admin")
    for r in (client.get("/api/v1/users", headers=_h(s["access_token"])),
              client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})):
        assert "no-store" in r.headers["Cache-Control"]
        assert r.headers["Pragma"] == "no-cache"


# ---------------- Firma de perfil ----------------

def test_registro_de_firma_valida_y_vinculada_al_usuario_del_token(client, app):
    ids = _seed(app)
    t = _login(client, "tech")["access_token"]
    assert client.get("/api/v1/me/signature", headers=_h(t)).get_json()["signature"] is None
    r = client.post("/api/v1/me/signature", headers=_h(t), json={"image": _data_url(_signature_png()), "user_id": ids["tech2"]})
    assert r.status_code == 201
    sig = r.get_json()["signature"]
    assert sig["user_id"] == ids["tech"] and sig["version"] == 1 and "storage_key" not in sig
    img = client.get("/api/v1/me/signature/image", headers=_h(t))
    assert img.status_code == 200 and img.mimetype == "image/png" and img.data == _signature_png()
    # La firma no aparece para el otro tecnico.
    t2 = _login(client, "tech2")["access_token"]
    assert client.get("/api/v1/me/signature", headers=_h(t2)).get_json()["signature"] is None


@pytest.mark.parametrize("payload,code", [
    ({}, "signature_empty"),
    ({"image": _data_url(_png((300, 100), "white"))}, "signature_blank"),
    ({"image": "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff").decode()}, "signature_invalid_format"),
    ({"image": _data_url(b"no es png")}, "signature_invalid_format"),
    ({"image": _data_url(_png((10, 10), "black"))}, "signature_invalid_size"),
    ({"image": "%%%"}, "signature_invalid_format"),
])
def test_registro_de_firma_rechaza_datos_invalidos(client, app, payload, code):
    _seed(app)
    t = _login(client, "tech")["access_token"]
    r = client.post("/api/v1/me/signature", headers=_h(t), json=payload)
    assert r.status_code == 400 and r.get_json()["code"] == code


def test_solo_tecnicos_registran_firma(client, app):
    _seed(app)
    a = _login(client, "admin")["access_token"]
    assert client.post("/api/v1/me/signature", headers=_h(a), json={"image": _data_url(_signature_png())}).status_code == 403
    assert client.post("/api/v1/me/signature", json={"image": _data_url(_signature_png())}).status_code == 401


# ---------------- Firma historica inmutable ----------------

def test_evidencia_conserva_la_firma_original_al_cambiar_la_de_perfil(client, app):
    ids = _seed(app)
    disp = _login(client, "disp")["access_token"]
    t = _login(client, "tech")["access_token"]
    wo = _wo(client, disp, ids["tech"])
    assert _upload(client, t, wo).status_code == 409  # sin firma de perfil

    client.post("/api/v1/me/signature", headers=_h(t), json={"image": _data_url(_signature_png(0))})
    # Campos de firma enviados por el cliente se ignoran: el servidor usa la del usuario autenticado.
    r = _upload(client, t, wo, technician_signature_id="999", signature=(io.BytesIO(_signature_png(5)), "otra.png"))
    assert r.status_code == 201
    ev = r.get_json()
    first = ev["technician_signature"]
    assert first["technician_id"] == ids["tech"] and first["version"] == 1 and first["signed_at"]

    client.post("/api/v1/me/signature", headers=_h(t), json={"image": _data_url(_signature_png(3))})
    assert client.get("/api/v1/me/signature", headers=_h(t)).get_json()["signature"]["version"] == 2

    hist = client.get(f"/api/v1/evidences/{ev['id']}/technician-signature", headers=_h(disp))
    assert hist.status_code == 200 and hist.data == _signature_png(0)
    again = client.get(f"/api/v1/evidences/{ev['id']}", headers=_h(t)).get_json()["technician_signature"]
    assert again == first
    # Una evidencia nueva usa la version vigente.
    new = _upload(client, t, wo).get_json()["technician_signature"]
    assert new["version"] == 2


def test_firma_historica_no_se_modifica_ni_se_elimina(client, app):
    from app.evidence.models import VisitEvidence, TechnicianSignature, ImmutableRecordError
    ids = _seed(app)
    disp = _login(client, "disp")["access_token"]
    admin = _login(client, "admin")["access_token"]
    t = _login(client, "tech")["access_token"]
    wo = _wo(client, disp, ids["tech"])
    client.post("/api/v1/me/signature", headers=_h(t), json={"image": _data_url(_signature_png())})
    ev_id = _upload(client, t, wo).get_json()["id"]

    r = client.delete(f"/api/v1/evidences/{ev_id}", headers=_h(admin))
    assert r.status_code == 409 and r.get_json()["code"] == "signed_evidence_immutable"

    with app.app_context():
        ev = db.session.get(VisitEvidence, ev_id)
        for field, value in [("technician_signature_sha256", "0" * 64), ("technician_signature_id", None),
                             ("technician_signature_user_id", ids["tech2"])]:
            setattr(ev, field, value)
            with pytest.raises(ImmutableRecordError):
                db.session.commit()
            db.session.rollback()
            ev = db.session.get(VisitEvidence, ev_id)
        sig = db.session.get(TechnicianSignature, ev.technician_signature_id)
        sig.sha256 = "f" * 64
        with pytest.raises(ImmutableRecordError):
            db.session.commit()
        db.session.rollback()
        sig = db.session.get(TechnicianSignature, ev.technician_signature_id)
        db.session.delete(sig)
        with pytest.raises(ImmutableRecordError):
            db.session.commit()
        db.session.rollback()
        assert db.session.get(VisitEvidence, ev_id).technician_signature_id is not None


def test_firma_historica_alterada_en_disco_se_detecta(client, app):
    from app.evidence.models import TechnicianSignature
    from app.evidence.storage import get_storage
    ids = _seed(app)
    disp = _login(client, "disp")["access_token"]
    t = _login(client, "tech")["access_token"]
    wo = _wo(client, disp, ids["tech"])
    client.post("/api/v1/me/signature", headers=_h(t), json={"image": _data_url(_signature_png())})
    ev_id = _upload(client, t, wo).get_json()["id"]
    with app.app_context():
        key = TechnicianSignature.query.filter_by(user_id=ids["tech"]).one().storage_key
        get_storage().load(key).write_bytes(_signature_png(7))
    r = client.get(f"/api/v1/evidences/{ev_id}/technician-signature", headers=_h(disp))
    assert r.status_code == 409 and r.get_json()["code"] == "signature_integrity_error"


def test_firma_de_evidencia_respeta_el_acceso_a_la_orden(client, app):
    ids = _seed(app)
    disp = _login(client, "disp")["access_token"]
    t = _login(client, "tech")["access_token"]
    t2 = _login(client, "tech2")["access_token"]
    wo = _wo(client, disp, ids["tech"])
    client.post("/api/v1/me/signature", headers=_h(t), json={"image": _data_url(_signature_png())})
    ev_id = _upload(client, t, wo).get_json()["id"]
    assert client.get(f"/api/v1/evidences/{ev_id}/technician-signature", headers=_h(t2)).status_code == 403
    assert client.get(f"/api/v1/evidences/{ev_id}/technician-signature", headers=_h(t)).status_code == 200


def test_evidencia_de_coordinador_sin_firma_de_tecnico(client, app):
    ids = _seed(app)
    disp = _login(client, "disp")["access_token"]
    wo = _wo(client, disp, ids["tech"])
    r = _upload(client, disp, wo)
    assert r.status_code == 201 and r.get_json()["technician_signature"] is None


# ---------------- Listado por orden ----------------

def test_listado_de_evidencias_por_orden_filtros_y_paginacion(client, app):
    from app.evidence.models import VisitEvidence
    ids = _seed(app)
    disp = _login(client, "disp")["access_token"]
    t = _login(client, "tech")["access_token"]
    t2 = _login(client, "tech2")["access_token"]
    for tok in (t, t2):
        client.post("/api/v1/me/signature", headers=_h(tok), json={"image": _data_url(_signature_png())})
    wo_a = _wo(client, disp, ids["tech"], "Instalacion fibra")
    wo_b = _wo(client, disp, ids["tech2"], "Mantenimiento")
    wo_empty = _wo(client, disp, ids["tech"], "Sin evidencias")
    for _ in range(3):
        _upload(client, t, wo_a)
    _upload(client, t2, wo_b)
    with app.app_context():
        # wo_b registrado ayer: permite probar filtro de fecha y orden.
        for ev in VisitEvidence.query.filter_by(work_order_id=wo_b).all():
            ev.received_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.session.commit()

    h = _h(disp)
    data = client.get("/api/v1/evidences/orders", headers=h).get_json()
    assert data["total"] == 3
    ids_desc = [i["work_order"]["id"] for i in data["items"]]
    assert ids_desc == [wo_a, wo_b, wo_empty]  # sin evidencias al final
    first = data["items"][0]
    assert first["evidence_count"] == 3 and first["technician"]["username"] == "tech"
    assert first["work_order"]["code"] == f"OS-{wo_a:04d}" and first["validation_status"] == "DRAFT"
    assert data["items"][2]["evidence_count"] == 0 and data["items"][2]["last_evidence_at"] is None
    # Las respuestas no incluyen archivos ni claves de almacenamiento.
    assert "storage_key" not in str(data)

    asc = client.get("/api/v1/evidences/orders?order=asc", headers=h).get_json()
    assert [i["work_order"]["id"] for i in asc["items"]] == [wo_b, wo_a, wo_empty]
    assert [i["work_order"]["id"] for i in client.get(f"/api/v1/evidences/orders?q=OS-{wo_b:04d}", headers=h).get_json()["items"]] == [wo_b]
    assert [i["work_order"]["id"] for i in client.get(f"/api/v1/evidences/orders?q={wo_a}", headers=h).get_json()["items"]] == [wo_a]
    assert [i["work_order"]["id"] for i in client.get("/api/v1/evidences/orders?q=fibra", headers=h).get_json()["items"]] == [wo_a]
    by_tech = client.get(f"/api/v1/evidences/orders?technician_id={ids['tech2']}", headers=h).get_json()
    assert [i["work_order"]["id"] for i in by_tech["items"]] == [wo_b]
    today = datetime.now(timezone.utc).date().isoformat()
    by_date = client.get(f"/api/v1/evidences/orders?date_from={today}&date_to={today}", headers=h).get_json()
    assert [i["work_order"]["id"] for i in by_date["items"]] == [wo_a]
    with_ev = client.get("/api/v1/evidences/orders?with_evidence=1", headers=h).get_json()
    assert with_ev["total"] == 2
    page2 = client.get("/api/v1/evidences/orders?page=2&page_size=2", headers=h).get_json()
    assert page2["total"] == 3 and [i["work_order"]["id"] for i in page2["items"]] == [wo_empty]
    assert client.get("/api/v1/evidences/orders?date_from=ayer", headers=h).status_code == 400
