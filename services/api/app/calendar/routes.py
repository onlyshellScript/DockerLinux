# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.identity.decorators import require_auth, require_role
from app.calendar import service

blueprint = Blueprint("calendar", __name__)


@blueprint.get("/calendar/events")
@require_auth
def events():
    roles = request.user_roles
    from_dt = request.args.get("from")
    to_dt = request.args.get("to")
    filters = {
        "technician_id": request.args.get("technician_id"),
        "status": request.args.get("status"),
        "type": request.args.get("type"),
        "priority": request.args.get("priority"),
        "city_id": request.args.get("city_id"),
        "zone_id": request.args.get("zone_id"),
        "include_cancelled": request.args.get("include_cancelled", "false").lower() == "true",
    }
    # technician role scoping
    for_user_id = None
    if "admin" not in roles and "dispatcher" not in roles:
        for_user_id = request.user_id
    items, err = service.list_events(from_dt, to_dt, filters, for_user_id, roles)
    if err == "invalid_range":
        return jsonify({"error": "invalid range"}), 422
    if err == "range_too_large":
        return jsonify({"error": "range too large"}), 422
    return jsonify({"items": items}), 200


@blueprint.get("/calendar/unassigned")
@require_auth
def unassigned():
    roles = request.user_roles
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    for_user_id = None
    if "admin" not in roles and "dispatcher" not in roles:
        for_user_id = request.user_id
    data, err = service.list_unassigned(page, page_size, for_user_id, roles)
    return jsonify(data), 200


@blueprint.post("/calendar/validate")
@require_auth
def validate():
    roles = request.user_roles
    data = request.get_json() or {}
    order_id = data.get("order_id")
    if order_id is None:
        return jsonify({"error": "order_id required"}), 422
    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid order_id"}), 422
    result, err = service.validate_schedule(order_id, data, roles)
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    return jsonify(result), 200


@blueprint.post("/calendar/authorize-sunday")
@require_role("admin")
def authorize_sunday():
    data = request.get_json() or {}
    order_id = data.get("order_id")
    if order_id is None:
        return jsonify({"error": "order_id required"}), 422
    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid order_id"}), 422
    if not data.get("reason"):
        return jsonify({"error": "reason required"}), 422
    if not data.get("authorize_sunday"):
        return jsonify({"error": "authorize_sunday required"}), 422
    from app.identity.models import User
    user = db.session.get(User, request.user_id)
    result, err = service.schedule_order(order_id, data, user, request.user_roles)
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result.to_dict() if hasattr(result, "to_dict") else result), 200
@blueprint.get("/technicians/<int:tid>/availability")
@require_auth
def availability(tid):
    roles = request.user_roles
    if "admin" not in roles and "dispatcher" not in roles:
        # technician can only view own
        from app.materials.models import TechnicianProfile
        prof = TechnicianProfile.query.filter_by(user_id=request.user_id).first()
        if not prof or prof.user_id != tid and prof.id != tid:
            # allow if tid matches user_id
            if tid != request.user_id:
                return jsonify({"error": "forbidden"}), 403
    from_dt = request.args.get("from")
    to_dt = request.args.get("to")
    data, err = service.technician_availability(tid, from_dt, to_dt)
    if err:
        return jsonify({"error": err}), 422
    return jsonify(data), 200

