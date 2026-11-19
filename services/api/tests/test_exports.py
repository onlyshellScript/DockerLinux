# Motor de exportaciones: catalogo, permisos, vista previa, generacion PDF/XLSX de TODAS las plantillas,
# tipos de dato en Excel, encabezados repetidos/paginacion en PDF, datos vacios, volumen, cambios entre
# vista previa y generacion, inyeccion de formulas y auditoria.
import io
import json
from datetime import datetime, timedelta, timezone

import pytest
from openpyxl import load_workbook

from app.extensions import db
from app.exports.templates import TEMPLATES
from app.identity.models import Role, User

PW = "Admin12345!"


def _seed(app, orders=12):
    from app.evidence.models import VisitEvidence, VisitSignature
    from app.materials.models import Material, MaterialRequest, MaterialRequestItem, TechnicianProfile
    from app.workorders.models import WorkOrder, WorkOrderStatusHistory
    with app.app_context():
        roles = {n: Role(name=n, description=n) for n in ("admin", "dispatcher", "technician")}
        db.session.add_all(roles.values())
        mk = lambda name, role: User(username=name, email=f"{name}@test.local", roles=[roles[role]])
        admin, disp, tech = mk("admin", "admin"), mk("coord", "dispatcher"), mk("tec1", "technician")
        for u in (admin, disp, tech):
            u.set_password(PW)
        db.session.add_all([admin, disp, tech])
        db.session.flush()
        prof = TechnicianProfile(user_id=tech.id, first_name="Ana", last_name="Pérez", phone="3001234567", specialty="Gas",
                                 is_available=True, is_active=True, open_orders=0)
        db.session.add(prof)
        mats = [
            Material(name="Tubo PEALPE 1/2", code="M-001", unit="m", current_stock=120, min_stock=50, unit_price=4500, is_active=True),
            Material(name="Regulador", code="M-002", unit="un", current_stock=3, min_stock=10, unit_price=85000.5, is_active=True),
            Material(name="=HYPERLINK(\"http://x\")", code="M-003", unit="un", current_stock=0, min_stock=5, unit_price=1200, is_active=True),
        ]
        db.session.add_all(mats)
        now = datetime.now(timezone.utc)
        statuses = ["pending", "assigned", "in_progress", "completed", "cancelled"]
        wos = []
        for i in range(orders):
            st = statuses[i % len(statuses)]
            wo = WorkOrder(title=f"Instalación {i}", customer_name=f"Cliente {i}", created_by_id=disp.id, status=st, priority=["high", "medium", "low"][i % 3],
                           assigned_to_id=tech.id if st != "pending" else None, zone="Norte" if i % 2 else "Sur",
                           created_at=now - timedelta(days=i % 6), completed_at=now if st == "completed" else None)
            db.session.add(wo)
            wos.append(wo)
        db.session.flush()
        for wo in wos[:4]:
            db.session.add(WorkOrderStatusHistory(work_order_id=wo.id, from_status="assigned", to_status="in_progress", changed_by_id=tech.id, created_at=now))
        req = MaterialRequest(requester_id=tech.id, technician_id=prof.id, work_order_id=wos[0].id, status="SUBMITTED", reason="Faltante", created_at=now - timedelta(days=2))
        done = MaterialRequest(requester_id=tech.id, technician_id=prof.id, work_order_id=wos[1].id, status="DELIVERED", created_at=now - timedelta(days=1))
        db.session.add_all([req, done])
        db.session.flush()
        db.session.add_all([
            MaterialRequestItem(request_id=req.id, material_id=1, quantity=5, quantity_requested=5, quantity_approved=0, quantity_delivered=0),
            MaterialRequestItem(request_id=done.id, material_id=2, quantity=4, quantity_requested=4, quantity_approved=4, quantity_delivered=4),
        ])
        for cat in ("BEFORE", "AFTER"):
            db.session.add(VisitEvidence(work_order_id=wos[2].id, category=cat, original_name=f"{cat.lower()}.jpg", mime_type="image/jpeg",
                                         size_bytes=20480, uploaded_by_id=tech.id, status="SUBMITTED", version_number=1, received_at=now))
        db.session.add(VisitSignature(work_order_id=wos[2].id, signer_name="Cliente 2", refused=False, received_at=now))
        db.session.commit()


def _h(client, user="admin"):
    r = client.post("/api/v1/auth/login", json={"username": user, "password": PW})
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _gen(client, h, tid, fmt, params=None, **extra):
    return client.post("/api/v1/exports/generate", headers=h, json={"template": tid, "format": fmt, "params": params or {}, **extra})


def test_catalog_filters_by_module_format_and_role(client, app):
    _seed(app)
    h = _h(client)
    ids = {t["id"] for t in client.get("/api/v1/exports/templates", headers=h).get_json()}
    assert ids == {t.id for t in TEMPLATES} and len(ids) == 18
    mats = client.get("/api/v1/exports/templates?module=materials&format=xlsx", headers=h).get_json()
    assert {t["id"] for t in mats} == {"materials.inventory", "materials.valued", "materials.critical"}
    hd = _h(client, "coord")
    coord_ids = {t["id"] for t in client.get("/api/v1/exports/templates", headers=hd).get_json()}
    assert "users.directory" not in coord_ids and "orders.general" in coord_ids
    assert client.get("/api/v1/exports/templates", headers=_h(client, "tec1")).status_code == 403


@pytest.mark.parametrize("tid", [t.id for t in TEMPLATES])
@pytest.mark.parametrize("fmt", ["pdf", "xlsx"])
def test_every_template_generates_valid_file(client, app, tid, fmt):
    _seed(app)
    h = _h(client)
    r = _gen(client, h, tid, fmt)
    assert r.status_code == 200, r.get_json()
    name = r.headers["X-Export-Filename"]
    assert name.startswith("sigos_") and name.endswith("." + fmt) and "no-store" in r.headers["Cache-Control"]
    rows = int(r.headers["X-Export-Rows"])
    if fmt == "pdf":
        assert r.data.startswith(b"%PDF-") and b"%%EOF" in r.data[-1024:]
    else:
        wb = load_workbook(io.BytesIO(r.data))
        assert wb.sheetnames == ["Resumen", "Datos"]
        ws = wb["Datos"]
        assert ws.freeze_panes == "A6"
        assert ws.max_row - 5 == max(rows, 1) or rows == 0


def test_xlsx_keeps_real_types_and_blocks_formula_injection(client, app):
    _seed(app)
    h = _h(client)
    r = _gen(client, h, "materials.valued", "xlsx", {}, )
    wb = load_workbook(io.BytesIO(r.data))
    ws = wb["Datos"]
    headers = [c.value for c in ws[5]]
    col = {h_: i for i, h_ in enumerate(headers)}
    data = list(ws.iter_rows(min_row=6, values_only=False))
    price = data[0][col["Precio unitario"]]
    assert isinstance(price.value, (int, float)) and not isinstance(price.value, bool) and price.number_format == '"$" #,##0'
    assert isinstance(data[0][col["Stock"]].value, (int, float))  # numero, no texto
    assert len(ws.tables) == 1  # tabla estructurada con filtros automaticos
    injected = [row[col["Material"]] for row in data if str(row[col["Material"]].value).startswith("=")]
    assert injected and injected[0].data_type == "s"  # texto, no formula
    total = wb["Resumen"]
    formulas = [c.value for c in total["B"] if isinstance(c.value, str) and c.value.startswith("=SUM(Datos!")]
    assert formulas  # total monetario con formula sobre la hoja Datos

    r = _gen(client, h, "orders.general", "xlsx", {"columns": ["code", "created_at"]})
    ws = load_workbook(io.BytesIO(r.data))["Datos"]
    assert [c.value for c in ws[5]] == ["Orden", "Creada"]
    assert isinstance(ws["B6"].value, datetime) and ws["B6"].number_format == "dd/mm/yyyy hh:mm"


def test_preview_matches_generation_and_detects_changes(client, app):
    _seed(app)
    h = _h(client)
    p = client.post("/api/v1/exports/preview", headers=h, json={"template": "orders.general", "format": "pdf", "params": {"status": "completed"}}).get_json()
    assert p["total"] >= 1 and all(row[p["columns"].index(next(c for c in p["columns"] if c["key"] == "status"))] == "Completada" for row in p["rows"])
    assert _gen(client, h, "orders.general", "pdf", {"status": "completed"}, expected_hash=p["hash"]).status_code == 200
    with app.app_context():
        from app.workorders.models import WorkOrder
        db.session.add(WorkOrder(title="Nueva", created_by_id=1, status="completed", priority="low"))
        db.session.commit()
    r = _gen(client, h, "orders.general", "pdf", {"status": "completed"}, expected_hash=p["hash"])
    assert r.status_code == 409 and r.get_json()["code"] == "DATA_CHANGED"
    assert _gen(client, h, "orders.general", "pdf", {"status": "completed"}, expected_hash=p["hash"], accept_changes=True).status_code == 200


def test_validation_errors(client, app):
    _seed(app)
    h = _h(client)
    assert _gen(client, h, "nope", "pdf").status_code == 422
    assert _gen(client, h, "orders.general", "docx").status_code == 422
    assert _gen(client, h, "orders.general", "pdf", {"status": "inventado"}).get_json()["field"] == "status"
    assert _gen(client, h, "orders.general", "pdf", {"columns": ["code", "password_hash"]}).get_json()["field"] == "columns"
    assert _gen(client, h, "orders.general", "pdf", {"date_from": "2026-12-01", "date_to": "2026-01-01"}).get_json()["field"] == "date_from"
    assert _gen(client, h, "orders.general", "pdf", {"sort": "inexistente"}).get_json()["field"] == "sort"


def test_permissions_and_no_sensitive_data(client, app):
    _seed(app)
    hd = _h(client, "coord")
    assert _gen(client, hd, "users.directory", "xlsx").status_code == 403
    r = _gen(client, _h(client), "users.directory", "xlsx", {"columns": ["username", "email", "roles", "status", "must_change", "created_at", "last_login"]})
    wb = load_workbook(io.BytesIO(r.data))
    text = " ".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None)
    assert "pbkdf2" not in text and "scrypt" not in text and PW not in text


def test_empty_dataset_and_filters(client, app):
    _seed(app)
    h = _h(client)
    params = {"date_from": "2020-01-01", "date_to": "2020-01-02"}
    p = client.post("/api/v1/exports/preview", headers=h, json={"template": "orders.general", "format": "xlsx", "params": params}).get_json()
    assert p["total"] == 0 and p["rows"] == []
    r = _gen(client, h, "orders.general", "xlsx", params)
    ws = load_workbook(io.BytesIO(r.data))["Datos"]
    assert r.status_code == 200 and "Sin registros" in str(ws["A6"].value)
    assert _gen(client, h, "orders.general", "pdf", params).status_code == 200
    crit = client.post("/api/v1/exports/preview", headers=h, json={"template": "materials.critical", "format": "pdf", "params": {}}).get_json()
    assert crit["total"] == 2  # Regulador (bajo) y el material sin stock; el de stock normal no aparece


def test_large_volume_multipage_pdf_and_xlsx(client, app):
    _seed(app, orders=1200)
    h = _h(client)
    r = _gen(client, h, "orders.general", "pdf")
    assert r.status_code == 200
    pages = r.data.count(b"/Type /Page") - r.data.count(b"/Type /Pages")
    assert pages > 20
    r = _gen(client, h, "orders.general", "xlsx")
    ws = load_workbook(io.BytesIO(r.data))["Datos"]
    assert ws.max_row - 5 == 1200


def test_export_is_audited(client, app):
    _seed(app)
    h = _h(client)
    _gen(client, h, "materials.inventory", "pdf")
    with app.app_context():
        from app.settings.models import AuditLog
        row = AuditLog.query.filter_by(section="export").one()
        detail = json.loads(row.new_value)
        assert row.username == "admin" and detail["template"] == "materials.inventory" and detail["format"] == "pdf" and detail["rows"] == 3
