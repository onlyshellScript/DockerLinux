# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.identity.decorators import require_auth, require_role
from app.identity.models import User
from app.materials.models import ALL_MOVEMENTS
from app.materials.service import (
    create_material,
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

@blueprint.get("/materials")
@require_auth
def materials_list():
    is_active = request.args.get("is_active")
    if is_active is not None:
        is_active = is_active.lower() == "true"
    materials = list_materials(is_active=is_active)
    return jsonify([m.to_dict() for m in materials]), 200


@blueprint.post("/materials")
@require_role("admin", "dispatcher")
def materials_create():
    data = request.get_json()
    if not data or not data.get("name") or not data.get("unit"):
        return jsonify({"error": "name and unit required"}), 400
    m = create_material(data)
    return jsonify(m.to_dict()), 201


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
        return jsonify({"error": "request body required"}), 400
    m = update_material(mat_id, data)
    if not m:
        return jsonify({"error": "material not found"}), 404
    return jsonify(m.to_dict()), 200


# ---- Stock movements ----

@blueprint.post("/materials/<int:mat_id>/movements")
@require_role("admin", "dispatcher")
def materials_movement(mat_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400
    quantity = data.get("quantity")
    movement_type = data.get("movement_type")
    if quantity is None or quantity <= 0:
        return jsonify({"error": "positive quantity required"}), 400
    if movement_type not in ALL_MOVEMENTS:
        return jsonify({"error": "invalid movement_type"}), 400
    mv, error = register_movement(
        mat_id, quantity, movement_type, request.user_id,
        work_order_id=data.get("work_order_id"), notes=data.get("notes"),
    )
    if error == "not_found":
        return jsonify({"error": "material not found"}), 404
    if error == "insufficient_stock":
        return jsonify({"error": "insufficient stock"}), 400
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
