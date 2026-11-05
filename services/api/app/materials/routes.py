# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.settings import service as settings_service
from app.common.normalize import normalize_text
from app.identity.decorators import require_auth, require_role
from app.identity.models import User
from app.workorders.models import WorkOrder
from app.materials.models import TechnicianProfile
from app.materials.models import ALL_MOVEMENTS, MOVEMENT_ADJUSTMENT
from app.materials.service import (
    create_material,
    material_status,
    list_materials,
    get_material,
    update_material,
    register_movement,
    get_movements,
    create_profile,
    list_profiles,
    get_profile,
    update_profile,
    transfer_stock,
    consume_for_order,
    get_technician_stock,
    create_material_request,
    approve_request,
    reject_request,
    deliver_request,
    list_requests,
)

blueprint = Blueprint("materials", __name__)


# ---- Materials ----

# ---- Catalog (read) ----

@blueprint.get("/material-categories")
@require_auth
def categories_list():
    from app.materials.models import MaterialCategory
    rows = MaterialCategory.query.filter_by(is_active=True).order_by(MaterialCategory.name).all()
    return jsonify([r.to_dict() for r in rows]), 200


@blueprint.get("/material-units")
@require_auth
def units_list():
    from app.materials.models import MaterialUnit
    rows = MaterialUnit.query.filter_by(is_active=True).order_by(MaterialUnit.name).all()
    return jsonify([r.to_dict() for r in rows]), 200


@blueprint.get("/material-catalog")
@require_auth
def catalog_list():
    from app.materials.models import MaterialCatalog, MaterialCategory, MaterialUnit
    q = request.args.get("q")
    category = request.args.get("category")
    available = request.args.get("available")
    stage = request.args.get("stage")
    applies_to = request.args.get("applies_to")
    query = MaterialCatalog.query.filter_by(is_active=True)
    if category:
        cat = MaterialCategory.query.filter_by(code=category).first()
        if cat:
            query = query.filter_by(category_id=cat.id)
    if stage:
        query = query.filter_by(stage=stage)
    if applies_to:
        query = query.filter_by(applies_to=applies_to)
    if q:
        nq = normalize_text(q)
        query = query.filter(db.func.lower(MaterialCatalog.name).contains(nq) | db.func.lower(MaterialCatalog.code).contains(nq))
    rows = query.order_by(MaterialCatalog.name).all()
    if available is not None:
        avail = available.lower() == "true"
        inv_ids = {m.catalog_item_id for m in Material.query.filter(Material.catalog_item_id.isnot(None)).all()}
        filtered = []
        for r in rows:
            is_avail = r.id not in inv_ids
            if is_avail == avail:
                filtered.append(r)
        rows = filtered
    return jsonify([r.to_dict() for r in rows]), 200


@blueprint.post("/material-catalog")
@require_role("admin")
def catalog_create():
    from app.materials.models import MaterialCatalog, MaterialCategory, MaterialUnit
    data = request.get_json() or {}
    if not data.get("category_id") or not data.get("code") or not data.get("name") or not data.get("unit_id"):
        return jsonify({"error": "category_id, code, name, unit_id required", "message": "category_id, code, name, unit_id required"}), 422
    # duplicate normalized name
    nn = normalize_text(data["name"])
    if MaterialCatalog.query.filter_by(name_norm=nn).first():
        return jsonify({"error": "duplicate name", "message": "duplicate name", "code": "DUPLICATE_NAME"}), 409
    if MaterialCatalog.query.filter_by(code=data["code"]).first():
        return jsonify({"error": "duplicate code", "message": "duplicate code", "code": "DUPLICATE_CODE"}), 409
    # similar names warning (not blocking): check contains
    similar = MaterialCatalog.query.filter(MaterialCatalog.name_norm.contains(nn[:8])).all() if len(nn) >= 4 else []
    ci = MaterialCatalog(
        category_id=int(data["category_id"]),
        code=data["code"].strip(),
        name=data["name"].strip(),
        name_norm=nn,
        unit_id=int(data["unit_id"]),
        measure=data.get("measure"),
        stage=data.get("stage"),
        applies_to=data.get("applies_to"),
        is_active=True,
    )
    db.session.add(ci)
    db.session.commit()
    resp = ci.to_dict()
    if similar:
        resp["similar"] = [s.name for s in similar[:5]]
    return jsonify(resp), 201


@blueprint.get("/materials")
@require_auth
def materials_list():
    is_active = request.args.get("is_active")
    if is_active is not None:
        is_active = is_active.lower() == "true"
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    q = request.args.get("q")
    status = request.args.get("status")
    unit = request.args.get("unit")
    sort = request.args.get("sort", "name")
    order = request.args.get("order", "asc")
    result = list_materials(q=q, status=status, unit=unit, is_active=is_active, page=page, page_size=page_size, sort=sort, order=order)
    items = []
    for row in result["items"]:
        m = row["material"]
        d = m.to_dict()
        d["status"] = row["status"]
        items.append(d)
    return jsonify({
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "counts": result["counts"],
        "total_value": float(result["total_value"]),
    }), 200


@blueprint.post("/materials")
@require_role("admin", "dispatcher")
def materials_create():
    data = request.get_json() or {}
    # reject free-text fields
    if any(k in data for k in ("name", "code", "unit")):
        return jsonify({"error": "free-text fields not allowed; use catalog_item_id",
                       "message": "free-text fields not allowed; use catalog_item_id", "code": "FREE_TEXT_NOT_ALLOWED"}), 422
    if not data.get("catalog_item_id"):
        return jsonify({"error": "catalog_item_id required", "message": "catalog_item_id required"}), 422
    data = dict(data)
    data["user_id"] = getattr(request, "user_id", None)
    try:
        m = create_material(data)
    except ValueError as e:
        msg = str(e)
        if msg == "already_inventoried":
            return jsonify({"error": "already inventoried", "message": "already inventoried", "code": "ALREADY_INVENTORIED"}), 409
        if msg == "catalog_item not found":
            return jsonify({"error": "catalog_item not found", "message": "catalog_item not found"}), 422
        return jsonify({"error": msg, "message": msg}), 422
    d = m.to_dict()
    d["status"] = material_status(m.current_stock, m.min_stock)
    return jsonify(d), 201


@blueprint.get("/materials/export")
@require_role("admin", "dispatcher")
def materials_export():
    is_active = request.args.get("is_active")
    if is_active is not None:
        is_active = is_active.lower() == "true"
    result = list_materials(q=request.args.get("q"), status=request.args.get("status"), unit=request.args.get("unit"),
                            is_active=is_active, page=1, page_size=100000, sort=request.args.get("sort","name"),
                            order=request.args.get("order","asc"))
    import csv, io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Codigo", "Nombre", "Unidad", "Stock", "Minimo", "Precio", "Estado"])
    for row in result["items"]:
        m = row["material"]
        writer.writerow([m.code, m.name, m.unit, m.current_stock, m.min_stock, m.unit_price, row["status"]])
    from flask import Response
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=materiales.csv"})




# ---- Export (Fase 3) ----
import base64

def _export_params():
    is_active = request.args.get("is_active")
    if is_active is not None:
        is_active = is_active.lower() == "true"
    filters = {
        "q": request.args.get("q"),
        "status": request.args.get("status"),
        "unit": request.args.get("unit"),
        "is_active": is_active,
        "category": request.args.get("category"),
        "sort": request.args.get("sort", "name"),
        "order": request.args.get("order", "asc"),
    }
    cols_raw = request.args.get("columns")
    if cols_raw:
        columns = [c.strip() for c in cols_raw.split(",") if c.strip()]
    else:
        columns = None
    fmt = (request.args.get("format") or "csv").lower()
    separator = request.args.get("separator", ";")
    orientation = request.args.get("orientation", "landscape")
    return filters, columns, fmt, separator, orientation


@blueprint.get("/materials/export/preview")
@require_role("admin", "dispatcher")
def materials_export_preview():
    from app.materials.export import ExportDataset, render_csv, render_excel, render_pdf
    filters, columns, fmt, separator, orientation = _export_params()
    user = db.session.get(User, request.user_id)
    ds = ExportDataset(filters=filters, columns=columns, user=user, limit=20)
    if fmt == "csv":
        content = render_csv(ds, separator=separator).decode("utf-8")
        return jsonify({"format": "csv", "content": content, "rows": ds.total_rows, "truncated": ds.truncated}), 200
    if fmt == "excel":
        # return first rows as grid for preview
        return jsonify({
            "format": "excel",
            "headers": ds.column_headers(),
            "rows": [ds.row_values(r) for r in ds.rows],
            "total_rows": ds.total_rows,
            "truncated": ds.truncated,
        }), 200
    if fmt == "pdf":
        pdf_bytes = render_pdf(ds, orientation=orientation)
        b64 = base64.b64encode(pdf_bytes).decode("ascii")
        return jsonify({"format": "pdf", "content_base64": b64, "rows": ds.total_rows, "truncated": ds.truncated}), 200
    return jsonify({"error": "invalid format", "message": "invalid format"}), 422


@blueprint.get("/materials/export/download")
@require_role("admin", "dispatcher")
def materials_export_download():
    from app.materials.export import ExportDataset, render_csv, render_excel, render_pdf
    filters, columns, fmt, separator, orientation = _export_params()
    user = db.session.get(User, request.user_id)
    ds = ExportDataset(filters=filters, columns=columns, user=user, limit=None)
    # row cap
    cap = 5000
    if ds.total_rows > cap:
        ds = ExportDataset(filters=filters, columns=columns, user=user, limit=cap)
        truncated = True
    else:
        truncated = ds.truncated
    if fmt == "csv":
        data = render_csv(ds, separator=separator)
        mimetype = "text/csv"
        ext = "csv"
    elif fmt == "excel":
        data = render_excel(ds)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    elif fmt == "pdf":
        data = render_pdf(ds, orientation=orientation)
        mimetype = "application/pdf"
        ext = "pdf"
    else:
        return jsonify({"error": "invalid format", "message": "invalid format"}), 422
    # audit
    try:
        settings_service.audit(request.user_id, user.username if user else None, "materials_export", fmt, None,
                              f"rows={ds.total_rows};cols={','.join(ds.columns)};truncated={truncated}", "applied",
                              request.headers.get("X-Request-Id"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    from flask import Response
    return Response(data, mimetype=mimetype,
                    headers={"Content-Disposition": f"attachment; filename=inventario.{ext}",
                             "X-Export-Rows": str(ds.total_rows),
                             "X-Export-Truncated": "1" if truncated else "0"})

@blueprint.get("/materials/<int:mat_id>")
@require_auth
def materials_get(mat_id):
    m = get_material(mat_id)
    if not m:
        return jsonify({"error": "material not found"}), 404
    return jsonify(m.to_dict()), 200


@blueprint.put("/materials/<int:mat_id>")
@require_role("admin", "dispatcher")
def materials_update(mat_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required", "message": "request body required"}), 400
    try:
        m = update_material(mat_id, data)
    except ValueError as e:
        msg = str(e)
        if msg in ("duplicate_code", "already_inventoried"):
            return jsonify({"error": msg, "message": msg, "code": msg.upper()}), 409
        return jsonify({"error": msg, "message": msg}), 422
    if not m:
        return jsonify({"error": "material not found", "message": "material not found"}), 404
    d = m.to_dict()
    d["status"] = material_status(m.current_stock, m.min_stock)
    return jsonify(d), 200


# ---- Stock movements ----

@blueprint.post("/materials/<int:mat_id>/movements")
@require_role("admin", "dispatcher")
def materials_movement(mat_id):
    data = request.get_json() or {}
    quantity = data.get("quantity")
    movement_type = data.get("movement_type")
    if quantity is None:
        return jsonify({"error": "quantity required", "message": "quantity required"}), 422
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid quantity", "message": "invalid quantity"}), 422
    if movement_type not in ALL_MOVEMENTS:
        return jsonify({"error": "invalid movement_type", "message": "invalid movement_type"}), 422
    if movement_type == MOVEMENT_ADJUSTMENT:
        if quantity == 0:
            return jsonify({"error": "quantity must not be zero", "message": "quantity must not be zero"}), 422
    else:
        if quantity <= 0:
            return jsonify({"error": "positive quantity required", "message": "positive quantity required"}), 422
    mv, error = register_movement(
        mat_id, quantity, movement_type, request.user_id,
        work_order_id=data.get("work_order_id"), notes=data.get("notes"),
    )
    if error == "not_found":
        return jsonify({"error": "material not found", "message": "material not found"}), 404
    if error == "insufficient_stock":
        return jsonify({"error": "insufficient stock", "message": "insufficient stock", "code": "INSUFFICIENT_STOCK"}), 409
    if error == "invalid_quantity":
        return jsonify({"error": "invalid quantity", "message": "invalid quantity"}), 422
    if error == "invalid_quantity_precision":
        return jsonify({"error": "quantity precision not allowed for unit", "message": "quantity precision not allowed for unit"}), 422
    if error:
        return jsonify({"error": error, "message": error}), 400
    return jsonify(mv.to_dict()), 201


@blueprint.get("/materials/<int:mat_id>/movements")
@require_auth
def materials_movements_list(mat_id):
    movements = get_movements(mat_id=mat_id)
    return jsonify([m.to_dict() for m in movements]), 200


# ---- Technician profiles ----

@blueprint.get("/technician-profiles")
@require_auth
def profiles_list():
    is_available = request.args.get("is_available")
    if is_available is not None:
        is_available = is_available.lower() == "true"
    profiles = list_profiles(is_available=is_available)
    return jsonify([p.to_dict() for p in profiles]), 200


@blueprint.post("/technician-profiles")
@require_role("admin")
def profiles_create():
    data = request.get_json()
    if not data or not data.get("user_id"):
        return jsonify({"error": "user_id required"}), 400
    user = db.session.get(User, data["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 400
    p = create_profile(data)
    return jsonify(p.to_dict()), 201


@blueprint.get("/technician-profiles/<int:profile_id>")
@require_auth
def profiles_get(profile_id):
    p = get_profile(profile_id)
    if not p:
        return jsonify({"error": "profile not found"}), 404
    return jsonify(p.to_dict()), 200


@blueprint.put("/technician-profiles/<int:profile_id>")
@require_role("admin", "dispatcher")
def profiles_update(profile_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400
    p = update_profile(profile_id, data)
    if not p:
        return jsonify({"error": "profile not found"}), 404
    return jsonify(p.to_dict()), 200


# ---- Transfers / technician stock ----

@blueprint.post("/materials/transfer")
@require_role("admin", "dispatcher")
def materials_transfer():
    data = request.get_json() or {}
    mat_id = data.get("material_id")
    tech_id = data.get("technician_id")
    qty = data.get("quantity")
    if not mat_id or not tech_id or not qty:
        return jsonify({"error": "material_id, technician_id, quantity required"}), 400
    res, err = transfer_stock(
        int(mat_id), int(tech_id), float(qty), request.user_id, data.get("notes"))
    if err == "material_not_found":
        return jsonify({"error": "material not found"}), 404
    if err == "technician_not_found":
        return jsonify({"error": "technician not found"}), 404
    if err == "insufficient_stock":
        return jsonify({"error": "insufficient stock"}), 400
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"ok": True}), 201


@blueprint.post("/materials/consume")
@require_role("admin", "dispatcher", "technician")
def materials_consume():
    data = request.get_json() or {}
    mat_id = data.get("material_id")
    tech_id = data.get("technician_id")
    qty = data.get("quantity")
    wo_id = data.get("work_order_id")
    if not mat_id or not tech_id or not qty or not wo_id:
        return jsonify({"error": "material_id, technician_id, quantity, work_order_id required"}), 400
    mv, err = consume_for_order(
        int(mat_id), int(tech_id), float(qty), int(wo_id), request.user_id, data.get("notes"))
    if err == "insufficient_stock":
        return jsonify({"error": "insufficient stock"}), 400
    if err:
        return jsonify({"error": err}), 400
    return jsonify(mv.to_dict()), 201


@blueprint.get("/technician-stock")
@require_auth
def technician_stock_list():
    tech_id = request.args.get("technician_id", type=int)
    if not tech_id:
        return jsonify({"error": "technician_id required"}), 400
    items = get_technician_stock(tech_id)
    return jsonify([i.to_dict() for i in items]), 200

# ---- Material requests ----

@blueprint.get("/material-requests")
@require_auth
def material_requests_list():
    status = request.args.get("status")
    reqs = list_requests(status=status)
    return jsonify([r.to_dict() for r in reqs]), 200


@blueprint.post("/material-requests")
@require_auth
def material_requests_create():
    data = request.get_json() or {}
    if not data.get("items"):
        return jsonify({"error": "items required"}), 400
    req = create_material_request(data, request.user_id)
    return jsonify(req.to_dict()), 201


@blueprint.post("/material-requests/<int:req_id>/approve")
@require_role("admin", "dispatcher")
def material_requests_approve(req_id):
    data = request.get_json() or {}
    req, err = approve_request(req_id, request.user_id, data.get("reason"))
    if err == "invalid_state":
        return jsonify({"error": "invalid state"}), 409
    if not req:
        return jsonify({"error": "not found"}), 404
    return jsonify(req.to_dict()), 200


@blueprint.post("/material-requests/<int:req_id>/reject")
@require_role("admin", "dispatcher")
def material_requests_reject(req_id):
    data = request.get_json() or {}
    req, err = reject_request(req_id, request.user_id, data.get("reason"))
    if err == "invalid_state":
        return jsonify({"error": "invalid state"}), 409
    if not req:
        return jsonify({"error": "not found"}), 404
    return jsonify(req.to_dict()), 200


@blueprint.post("/material-requests/<int:req_id>/deliver")
@require_role("admin", "dispatcher")
def material_requests_deliver(req_id):
    req, err = deliver_request(req_id, request.user_id)
    if err == "invalid_state":
        return jsonify({"error": "invalid state"}), 409
    if err == "insufficient_stock":
        return jsonify({"error": "insufficient stock"}), 400
    if not req:
        return jsonify({"error": "not found"}), 404
    return jsonify(req.to_dict()), 200


@blueprint.post("/work-orders/<int:wo_id>/materials")
@require_role("admin", "dispatcher", "technician")
def consume_work_order_material(wo_id):
    data = request.get_json() or {}
    mat_id = data.get("material_id")
    qty_raw = data.get("quantity")
    if not mat_id or qty_raw is None:
        return jsonify({"error": "material_id and quantity required", "message": "material_id and quantity required"}), 422
    try:
        qty = float(qty_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid quantity", "message": "invalid quantity"}), 422
    if qty <= 0:
        return jsonify({"error": "positive quantity required", "message": "positive quantity required"}), 422
    wo = db.session.get(WorkOrder, wo_id)
    if not wo:
        return jsonify({"error": "work order not found", "message": "work order not found"}), 404
    if wo.status in ("cancelled", "closed", "completed"):
        return jsonify({"error": "order does not accept materials", "message": "order does not accept materials", "code": "ORDER_NOT_ELIGIBLE"}), 409
    roles = getattr(request, "user_roles", [])
    if "technician" in roles and "admin" not in roles and "dispatcher" not in roles:
        if wo.assigned_to_id != request.user_id:
            return jsonify({"error": "forbidden", "message": "forbidden"}), 403
        profile = TechnicianProfile.query.filter_by(user_id=request.user_id).first()
        if not profile:
            return jsonify({"error": "technician profile not found", "message": "technician profile not found"}), 404
        tech_id = profile.id
    else:
        tech_id = data.get("technician_id")
        if not tech_id:
            return jsonify({"error": "technician_id required", "message": "technician_id required"}), 422
        tech_id = int(tech_id)
    mv, err = consume_for_order(int(mat_id), tech_id, qty, wo_id, request.user_id, data.get("notes"))
    if err == "insufficient_stock":
        return jsonify({"error": "insufficient stock", "message": "insufficient stock", "code": "INSUFFICIENT_STOCK"}), 409
    if err:
        return jsonify({"error": err, "message": err}), 400
    d = mv.to_dict()
    d["status"] = None
    return jsonify(d), 201
