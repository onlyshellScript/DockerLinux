# Módulo de la aplicación.
from flask import Blueprint, request, jsonify

from app.identity.decorators import require_auth
from app.workorders.models import WorkOrder
from app.workorders.service import get_work_order, record_used_materials
from app.materials.models import TechnicianProfile, TechnicianStock, Material
from app.extensions import db

blueprint = Blueprint("tecnico", __name__)


# _is_technician: indica si el usuario autenticado tiene el rol technician; sin parametros; salida bool; lee request.user_roles.
def _is_technician():
    return "technician" in (request.user_roles or [])


# GET /mi-dashboard (roles: autenticado): mi dashboard; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.get("/mi-dashboard")
@require_auth
def mi_dashboard():
    if not _is_technician():
        return jsonify({"error": "forbidden"}), 403
    uid = request.user_id
    wos = WorkOrder.query.filter_by(assigned_to_id=uid).all()
    counts = {}
    for w in wos:
        counts[w.status] = counts.get(w.status, 0) + 1
    return jsonify({
        "user_id": uid,
        "total": len(wos),
        "counts": counts,
        "orders": [w.to_dict() for w in wos],
    }), 200


# GET /mis-ordenes (roles: autenticado): mis ordenes; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.get("/mis-ordenes")
@require_auth
def mis_ordenes():
    if not _is_technician():
        return jsonify({"error": "forbidden"}), 403
    uid = request.user_id
    status = request.args.get("status")
    q = WorkOrder.query.filter_by(assigned_to_id=uid)
    if status:
        q = q.filter(WorkOrder.status == status)
    items = q.order_by(WorkOrder.created_at.desc()).all()
    return jsonify({"items": [w.to_dict() for w in items], "total": len(items)}), 200


# GET /mis-ordenes/<int:wo_id> (roles: autenticado): mis orden detalle; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.get("/mis-ordenes/<int:wo_id>")
@require_auth
def mis_orden_detalle(wo_id):
    if not _is_technician():
        return jsonify({"error": "forbidden"}), 403
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "not found"}), 404
    if wo.assigned_to_id != request.user_id:
        return jsonify({"error": "forbidden"}), 403
    return jsonify(wo.to_dict()), 200


# POST /mis-ordenes/<int:wo_id>/estado (roles: autenticado): mis orden estado; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/mis-ordenes/<int:wo_id>/estado")
@require_auth
def mis_orden_estado(wo_id):
    if not _is_technician():
        return jsonify({"error": "forbidden"}), 403
    from app.workorders.service import change_status
    from app.identity.models import User
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "not found"}), 404
    if wo.assigned_to_id != request.user_id:
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json() or {}
    to_status = data.get("to_status")
    if not to_status:
        return jsonify({"error": "to_status required"}), 400
    user = db.session.get(User, request.user_id)
    result, error = change_status(wo_id, to_status, user, data.get("notes"), data.get("reason"))
    if error == "not_found":
        return jsonify({"error": "not found"}), 404
    if error == "invalid_transition":
        return jsonify({"error": "invalid transition"}), 409
    if error == "reason_required":
        return jsonify({"error": "reason required"}), 422
    return jsonify(result.to_dict()), 200


# POST /mis-ordenes/<int:wo_id>/materiales (roles: autenticado): mis orden materiales; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/mis-ordenes/<int:wo_id>/materiales")
@require_auth
def mis_orden_materiales(wo_id):
    if not _is_technician():
        return jsonify({"error": "forbidden"}), 403
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "not found"}), 404
    if wo.assigned_to_id != request.user_id:
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json() or {}
    items = data.get("items") or data.get("materials") or []
    if not items:
        return jsonify({"error": "items required"}), 400
    from app.identity.models import User
    user = db.session.get(User, request.user_id)
    result, error = record_used_materials(wo_id, user, items)
    if error == "not_found":
        return jsonify({"error": "not found"}), 404
    if error == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if error == "invalid_material":
        return jsonify({"error": "invalid material"}), 400
    return jsonify(result.to_dict()), 200


# GET /mi-camioneta (roles: autenticado): mi camioneta; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.get("/mi-camioneta")
@require_auth
def mi_camioneta():
    if not _is_technician():
        return jsonify({"error": "forbidden"}), 403
    uid = request.user_id
    profile = TechnicianProfile.query.filter_by(user_id=uid).first()
    if not profile:
        return jsonify({"items": [], "total": 0}), 200
    stock = TechnicianStock.query.filter_by(technician_id=profile.id).all()
    items = []
    for s in stock:
        items.append({
            "material_id": s.material_id,
            "material": s.material.to_dict() if s.material else None,
            "quantity": s.quantity,
        })
    return jsonify({"items": items, "total": len(items)}), 200


# GET /mi-perfil (roles: autenticado): mi perfil; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.get("/mi-perfil")
@require_auth
def mi_perfil():
    if not _is_technician():
        return jsonify({"error": "forbidden"}), 403
    uid = request.user_id
    from app.materials.models import TechnicianProfile
    profile = TechnicianProfile.query.filter_by(user_id=uid).first()
    return jsonify(profile.to_dict() if profile else {}), 200