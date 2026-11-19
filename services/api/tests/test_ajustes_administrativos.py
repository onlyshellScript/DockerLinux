# Pruebas de los ajustes administrativos: revisión y aprobación de evidencias, cancelación lógica de órdenes y
# normalización a MAYÚSCULAS del módulo de materiales.
import base64
import io

import pytest
import sqlalchemy as sa
from PIL import Image, ImageDraw

from app.extensions import db
from app.identity.models import User, Role

PWD = "Pass12345!"


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buf, format="PNG")
    return buf.getvalue()


def _sig():
    img = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
    ImageDraw.Draw(img).line([(10, 80), (150, 10), (290, 70)], fill=(0, 0, 0, 255), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def env(app, client):
    with app.app_context():
        roles = {n: Role(name=n, description=n) for n in ("admin", "dispatcher", "technician")}
        db.session.add_all(roles.values())
        db.session.flush()
        ids = {}
        for name, rnames in [("admin", ["admin"]), ("admin2", ["admin", "technician"]), ("disp", ["dispatcher"]), ("tech", ["technician"])]:
            u = User(username=name, email=f"{name}@t.local")
            u.set_password(PWD)
            for r in rnames:
                u.roles.append(roles[r])
            db.session.add(u)
            db.session.flush()
            ids[name] = u.id
        db.session.commit()
    h = {n: {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"username": n, "password": PWD}).get_json()["access_token"]} for n in ids}
    for n in ("tech", "admin2"):
        assert client.post("/api/v1/me/signature", headers=h[n], json={"image": _sig()}).status_code == 201

    class E:
        pass
    e = E()
    e.ids, e.h, e.c = ids, h, client

    def order(assigned="tech", refusal=True):
        w = client.post("/api/v1/work-orders", headers=h["disp"], json={"title": "Orden", "assigned_to_id": ids[assigned]}).get_json()["id"]
        if refusal:
            client.post(f"/api/v1/work-orders/{w}/signatures", headers=h[assigned], json={"refused": True, "reason": "ausente"})
        return w

    def upload(w, who="tech"):
        r = client.post(f"/api/v1/work-orders/{w}/evidences", headers=h[who], data={"category": "BEFORE", "file": (io.BytesIO(_png()), "p.png")}, content_type="multipart/form-data")
        assert r.status_code == 201, r.get_json()
        return r.get_json()["id"]

    def post(w, action, who="admin", body=None):
        return client.post(f"/api/v1/work-orders/{w}/evidences/{action}", headers=h[who], json=body or {})

    e.order, e.upload, e.post = order, upload, post
    return e


# ---------------- Evidencias: revisión y aprobación ----------------

def test_aprobacion_registra_revisor_fecha_y_persiste(env, app, client):
    from app.evidence.models import EvidenceReview
    w = env.order()
    env.upload(w)
    assert env.post(w, "submit", "tech").status_code == 200
    r = env.post(w, "approve")
    assert r.status_code == 200 and r.get_json()["status"] == "APPROVED"
    with app.app_context():
        reviews = EvidenceReview.query.all()
        assert len(reviews) == 1 and reviews[0].reviewer_id == env.ids["admin"] and reviews[0].created_at
    # Aprobar de nuevo no duplica registros.
    assert env.post(w, "approve").status_code == 200
    with app.app_context():
        assert EvidenceReview.query.count() == 1
    # Persistencia tras volver a iniciar sesión.
    h2 = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"username": "admin", "password": PWD}).get_json()["access_token"]}
    d = client.get(f"/api/v1/work-orders/{w}/evidence-detail", headers=h2).get_json()
    assert d["status"] == "APPROVED"
    assert d["reviews"][0]["reviewer_username"] == "admin" and d["reviews"][0]["decision"] == "APPROVED"
    assert any(ev["action"] == "APPROVED" for ev in d["events"])


def test_aprobar_tras_correccion_con_evidencia_nueva(env):
    # Causa raíz: la foto agregada durante la corrección quedaba en borrador y bloqueaba la aprobación.
    w = env.order()
    env.upload(w)
    env.post(w, "submit", "tech")
    assert env.post(w, "request-correction", body={"notes": "falta foto del medidor"}).status_code == 200
    env.upload(w)
    assert env.post(w, "resubmit", "tech").status_code == 200
    r = env.post(w, "approve")
    assert r.status_code == 200, r.get_json()


def test_evidencias_sin_enviar_se_explican_y_luego_se_aprueban(env):
    w = env.order()
    env.upload(w)
    env.post(w, "submit", "tech")
    env.upload(w)  # agregada después del envío
    r = env.post(w, "approve")
    assert r.status_code == 409 and r.get_json()["code"] == "pending_drafts"
    assert "todavía no envió" in r.get_json()["error"]
    assert env.post(w, "submit", "tech").status_code == 200
    assert env.post(w, "approve").status_code == 200


def test_permisos_de_aprobacion(env):
    w = env.order()
    env.upload(w)
    env.post(w, "submit", "tech")
    assert env.post(w, "approve", "tech").status_code == 403
    assert env.post(w, "approve", "disp").status_code == 403
    assert env.post(w, "start-review", "disp").status_code == 200
    assert env.post(w, "approve").status_code == 200


def test_nadie_aprueba_sus_propias_evidencias(env):
    w = env.order(assigned="admin2")
    env.upload(w, who="admin2")
    env.post(w, "submit", "admin2")
    for action, body in [("approve", {}), ("reject", {"reason": "x"}), ("request-correction", {"notes": "x"})]:
        r = env.post(w, action, "admin2", body)
        assert r.status_code == 403 and r.get_json()["code"] == "own_evidence"
    assert env.post(w, "approve", "admin").status_code == 200


def test_aprobacion_de_inexistentes_y_estados_invalidos(env):
    assert env.post(999999, "approve").status_code == 404
    w = env.order()
    r = env.post(w, "approve")
    assert r.status_code == 404 and r.get_json()["code"] == "not_found"
    r = env.post(w, "resubmit", "tech")
    assert r.status_code == 409 and isinstance(r.get_json()["error"], str)
    env.upload(w)
    env.post(w, "submit", "tech")
    assert env.post(w, "reject", body={"reason": "ilegible"}).status_code == 200
    r = env.post(w, "approve")
    assert r.status_code == 409 and r.get_json()["code"] == "already_rejected"


# ---------------- Órdenes: cancelación lógica ----------------

def test_cancelacion_logica_por_administrador(env, app, client):
    from app.workorders.models import WorkOrder, WorkOrderStatusHistory
    from app.evidence.models import VisitEvidence
    w = env.order()
    ev = env.upload(w)
    chk = client.get(f"/api/v1/work-orders/{w}/cancellation", headers=env.h["admin"]).get_json()
    assert chk["can_cancel"] is True and chk["impacts"]["evidences"] == 1
    r = client.post(f"/api/v1/work-orders/{w}/cancel", headers=env.h["admin"], json={})  # motivo opcional
    assert r.status_code == 200 and r.get_json()["status"] == "cancelled"
    with app.app_context():
        wo = db.session.get(WorkOrder, w)
        assert wo is not None and wo.assigned_to_id == env.ids["tech"]
        assert db.session.get(VisitEvidence, ev) is not None
        h = WorkOrderStatusHistory.query.filter_by(work_order_id=w, to_status="cancelled").one()
        assert h.changed_by_id == env.ids["admin"] and h.from_status == "assigned" and h.created_at
    r = client.post(f"/api/v1/work-orders/{w}/cancel", headers=env.h["admin"], json={})
    assert r.status_code == 409 and r.get_json()["code"] == "already_cancelled" and "ya está cancelada" in r.get_json()["error"]


def test_cancelacion_con_motivo_e_impactos(env, app, client):
    from app.workorders.models import WorkOrder
    from app.materials.models import Material, MaterialRequest
    w = env.order()
    env.upload(w)
    env.post(w, "submit", "tech")
    env.post(w, "approve")
    with app.app_context():
        m = Material(name="cable", code="C1", unit="m", current_stock=10, min_stock=1, is_active=True)
        db.session.add(m)
        db.session.flush()
        mid = m.id
        db.session.add(MaterialRequest(work_order_id=w, requester_id=env.ids["tech"], status="SUBMITTED"))
        db.session.commit()
    client.post(f"/api/v1/materials/{mid}/movements", headers=env.h["admin"], json={"quantity": 2, "movement_type": "CONSUMPTION", "work_order_id": w})
    chk = client.get(f"/api/v1/work-orders/{w}/cancellation", headers=env.h["disp"]).get_json()
    assert chk["impacts"]["approved_evidences"] == 1 and chk["impacts"]["material_consumptions"] == 1
    assert chk["impacts"]["open_material_requests"] == 1
    r = client.post(f"/api/v1/work-orders/{w}/cancel", headers=env.h["disp"], json={"reason": "  Cliente desiste  "})
    assert r.status_code == 200
    with app.app_context():
        assert db.session.get(WorkOrder, w).cancel_reason == "Cliente desiste"
        assert db.session.get(Material, mid).current_stock == 8  # el consumo registrado se conserva
        assert MaterialRequest.query.filter_by(work_order_id=w).one().status == "SUBMITTED"  # no se cancela sola


def test_reglas_de_cancelacion(env, app, client):
    from app.workorders.models import WorkOrder
    w = env.order()
    with app.app_context():
        db.session.get(WorkOrder, w).status = "completed"
        db.session.commit()
    chk = client.get(f"/api/v1/work-orders/{w}/cancellation", headers=env.h["admin"]).get_json()
    assert chk["can_cancel"] is False and chk["blocked_code"] == "terminal_order"
    r = client.post(f"/api/v1/work-orders/{w}/cancel", headers=env.h["admin"], json={})
    assert r.status_code == 409 and r.get_json()["code"] == "terminal_order"
    assert client.post("/api/v1/work-orders/999999/cancel", headers=env.h["admin"], json={}).status_code == 404


def test_tecnico_no_cancela_por_ninguna_ruta(env, client):
    w = env.order()
    t = env.h["tech"]
    assert client.post(f"/api/v1/work-orders/{w}/cancel", headers=t, json={}).status_code == 403
    assert client.get(f"/api/v1/work-orders/{w}/cancellation", headers=t).status_code == 403
    assert client.post(f"/api/v1/work-orders/{w}/status", headers=t, json={"to_status": "cancelled", "reason": "x"}).status_code == 403
    assert client.post(f"/api/v1/work-orders/{w}/transitions", headers=t, json={"action": "cancel", "reason": "x"}).status_code == 403
    assert client.get(f"/api/v1/work-orders/{w}", headers=t).get_json()["status"] != "cancelled"


def test_admin_cancela_tambien_por_transicion(env, client):
    w = env.order()
    r = client.post(f"/api/v1/work-orders/{w}/transitions", headers=env.h["admin"], json={"action": "cancel", "reason": "duplicada"})
    assert r.status_code == 200 and r.get_json()["status"] == "cancelled"


# ---------------- Materiales: MAYÚSCULAS ----------------

@pytest.fixture
def catalog(app):
    from app.materials.models import MaterialCategory, MaterialUnit
    with app.app_context():
        cat = MaterialCategory(code="tub", name="tubería", name_norm="tuberia")
        unit = MaterialUnit(code="m", name="metro", name_norm="metro", allows_decimal=True)
        db.session.add_all([cat, unit])
        db.session.commit()
        return cat.id, unit.id


def test_catalogo_y_material_se_guardan_en_mayusculas(env, app, client, catalog):
    from app.materials.models import MaterialCategory, MaterialUnit
    cat_id, unit_id = catalog
    with app.app_context():
        assert db.session.get(MaterialCategory, cat_id).name == "TUBERÍA"
        assert db.session.get(MaterialUnit, unit_id).name == "METRO"
    r = client.post("/api/v1/material-catalog", headers=env.h["admin"], json={
        "category_id": cat_id, "unit_id": unit_id, "code": "tc-001", "name": "  tubería   de cobre ñandú ",
        "measure": "1/2 pulgada", "stage": "instalación", "applies_to": "residencial"})
    assert r.status_code == 201
    ci = r.get_json()
    assert ci["name"] == "TUBERÍA DE COBRE ÑANDÚ" and ci["measure"] == "1/2 PULGADA"
    assert ci["code"] == "tc-001"  # identificador técnico: conserva su formato
    r = client.post("/api/v1/materials", headers=env.h["admin"], json={"catalog_item_id": ci["id"], "min_stock": 1, "description": "para gas natural"})
    assert r.status_code == 201, r.get_json()
    m = r.get_json()
    assert m["name"] == "TUBERÍA DE COBRE ÑANDÚ" and m["description"] == "PARA GAS NATURAL" and m["unit"] == "M"
    # Edición: se normaliza.
    r = client.put(f"/api/v1/materials/{m['id']}", headers=env.h["admin"], json={"description": "  uso   exterior "})
    assert r.get_json()["description"] == "USO EXTERIOR"
    # Movimiento: notas normalizadas.
    r = client.post(f"/api/v1/materials/{m['id']}/movements", headers=env.h["admin"], json={"quantity": 3, "movement_type": "IN", "notes": "compra local"})
    assert r.status_code == 201 and r.get_json()["notes"] == "COMPRA LOCAL"
    # Filtros del catálogo con cualquier escritura.
    lst = client.get("/api/v1/material-catalog?stage=Instalación&applies_to=RESIDENCIAL", headers=env.h["admin"]).get_json()
    assert [x["id"] for x in lst] == [ci["id"]]


def test_duplicados_por_escritura_se_rechazan(env, app, client, catalog):
    from app.materials.models import Material
    cat_id, unit_id = catalog
    base = {"category_id": cat_id, "unit_id": unit_id}
    assert client.post("/api/v1/material-catalog", headers=env.h["admin"], json={**base, "code": "a1", "name": "Tornillo"}).status_code == 201
    for variant in ("TORNILLO", "tornillo", " TorNILLo ", "tornilló"):
        r = client.post("/api/v1/material-catalog", headers=env.h["admin"], json={**base, "code": "a-" + variant.strip(), "name": variant})
        assert r.status_code == 409, variant
    with app.app_context():
        a = Material(name="tuerca hexagonal", code="T1", unit="unidad", current_stock=1, min_stock=0)
        b = Material(name="arandela", code="T2", unit="unidad", current_stock=1, min_stock=0)
        db.session.add_all([a, b])
        db.session.commit()
        b_id = b.id
        assert a.name == "TUERCA HEXAGONAL"
    r = client.put(f"/api/v1/materials/{b_id}", headers=env.h["admin"], json={"name": "Tuerca  Hexagonal"})
    assert r.status_code == 409 and r.get_json()["code"] == "DUPLICATE_NAME"


def test_busqueda_sin_distinguir_mayusculas_ni_acentos(env, app, client):
    from app.materials.models import Material
    with app.app_context():
        db.session.add_all([Material(name="Tubería galvanizada", code="G1", unit="m", current_stock=5, min_stock=1),
                            Material(name="Codo", code="G2", unit="unidad", current_stock=5, min_stock=1)])
        db.session.commit()
    for q in ("tuberia", "TUBERÍA", "Tuberia Galv", "g1"):
        items = client.get(f"/api/v1/materials?q={q}", headers=env.h["admin"]).get_json()["items"]
        names = [i["material"]["name"] if "material" in i else i["name"] for i in items]
        assert names == ["TUBERÍA GALVANIZADA"], (q, names)


def test_script_normaliza_registros_existentes_sin_perder_relaciones(env, app):
    from app.materials.models import Material, StockMovement
    from maintenance.normalizar_materiales import run
    with app.app_context():
        # Registros heredados escritos sin pasar por el ORM (como en la base actual).
        db.session.execute(sa.text("INSERT INTO Materiales (Nombre, Codigo, Unidad, StockActual, StockMinimo, PrecioUnitario, EstaActivo, Descripcion) VALUES ('Tornillo', 'X1', 'unidad', 4, 0, 0, 1, 'acero  inox'), ('tornillo ', 'X2', 'unidad', 1, 0, 0, 1, NULL)"))
        ids = [r[0] for r in db.session.execute(sa.text("SELECT IdMaterial FROM Materiales WHERE Codigo IN ('X1','X2') ORDER BY Codigo")).all()]
        db.session.execute(sa.text("INSERT INTO MovimientosStock (IdMaterial, Cantidad, CantidadSolicitada, CantidadAprobada, CantidadEntregada, TipoMovimiento, IdUsuario, Notas) VALUES (:m, 4, 0, 0, 0, 'IN', :u, 'saldo inicial')"), {"m": ids[0], "u": env.ids["admin"]})
        db.session.commit()
        out = io.StringIO()
        report = run(apply=False, out=out)
        assert report["changes"]["Material"] == 2 and report["changes"]["StockMovement"] == 1
        dup = report["duplicates"][0]
        assert sorted(x["id"] for x in dup["materials"]) == sorted(ids) and any(x["movements"] == 1 for x in dup["materials"])
        db.session.expire_all()
        assert db.session.get(Material, ids[0]).name == "Tornillo"  # el informe no escribe
        run(apply=True, out=io.StringIO())
        db.session.expire_all()
        a, b = db.session.get(Material, ids[0]), db.session.get(Material, ids[1])
        assert (a.name, a.description, a.unit, b.name) == ("TORNILLO", "ACERO INOX", "UNIDAD", "TORNILLO")
        assert StockMovement.query.filter_by(material_id=ids[0]).one().notes == "SALDO INICIAL"
        assert Material.query.count() == 2  # no fusiona ni elimina
        assert run(apply=False, out=io.StringIO())["changes"]["Material"] == 0  # idempotente
