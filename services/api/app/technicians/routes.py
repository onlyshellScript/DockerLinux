from flask import Blueprint, request, jsonify

from app.extensions import db
from app.identity.decorators import require_auth, require_role
from app.identity.models import User, Role
from app.materials.models import TechnicianProfile
from app.technicians import service

blueprint = Blueprint("technicians", __name__)


def _profile_to_dict(p):
    d = p.to_dict()
    d["open_orders_count"] = p.open_orders
    return d


@blueprint.get("/technicians")
@require_auth
def list_technicians():
    # only admin/coordinator can view list; technician cannot
    roles = request.user_roles
    if "admin" not in roles and "dispatcher" not in roles:
        return jsonify({"error": "insufficient permissions"}), 403
    q = request.args.get("q")
    status = request.args.get("status")
    zone = request.args.get("zone")
    city_id = request.args.get("city_id")
    zone_id = request.args.get("zone_id")
    specialty = request.args.get("specialty")
    active = request.args.get("active")
    active_bool = None
    if active is not None:
        active_bool = active.lower() == "true"
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    result = service.list_technicians(q=q, status=status, zone=zone, city_id=city_id, zone_id=zone_id, specialty=specialty, active=active_bool, page=page, page_size=page_size)
    return jsonify({
        "items": [_profile_to_dict(p) for p in result["items"]],
        "total": result["total"],
        "counts": result["counts"],
    }), 200


@blueprint.get("/technicians/username-available")
@require_auth
def username_available():
    roles = request.user_roles
    if "admin" not in roles:
        return jsonify({"error": "insufficient permissions"}), 403
    username = request.args.get("username", "")
    return jsonify({"available": service.username_available(username)}), 200


@blueprint.post("/technicians")
@require_role("admin")
def create_technician():
    data = request.get_json() or {}
    if not data.get("first_name") or not data.get("last_name"):
        return jsonify({"error": "first_name, last_name required"}), 422
    if not data.get("document_type") or not data.get("document_number"):
        return jsonify({"error": "document_type, document_number required"}), 422
    result, err = service.create_technician(data, request.user_id)
    if err == "username_taken":
        return jsonify({"error": "username already exists"}), 409
    if err == "document_taken":
        return jsonify({"error": "document already exists"}), 409
    if err == "initial_password_not_configured":
        return jsonify({"error": "TECH_INITIAL_PASSWORD not configured"}), 500
    if err in ("invalid_specialty", "invalid_document_type", "invalid_city", "invalid_zone", "invalid_department", "invalid_municipality", "municipality_not_in_department", "invalid_coverage", "coverage_required", "too_many_coverages", "multiple_primary", "duplicate_coverage", "missing_fields", "missing_document"):
        return jsonify({"error": err}), 422
    if not result:
        return jsonify({"error": "could not create"}), 400
    profile = result["profile"]
    user = result["user"]
    return jsonify({
        "technician": _profile_to_dict(profile),
        "username": result["username"],
    }), 201


@blueprint.get("/technicians/<int:tid>")
@require_auth
def get_technician(tid):
    roles = request.user_roles
    p = service.get_technician(tid)
    if not p:
        return jsonify({"error": "not found"}), 404
    if "admin" not in roles and "dispatcher" not in roles:
        if "technician" not in roles or p.user_id != request.user_id:
            return jsonify({"error": "insufficient permissions"}), 403
    return jsonify(_profile_to_dict(p)), 200


@blueprint.patch("/technicians/<int:tid>")
@require_role("admin")
def patch_technician(tid):
    data = request.get_json() or {}
    profile, err = service.update_technician(tid, data, request.user_id)
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "username_taken":
        return jsonify({"error": "username already exists"}), 409
    if err == "document_taken":
        return jsonify({"error": "document already exists"}), 409
    if err == "password_not_allowed":
        return jsonify({"error": "password cannot be set from this module"}), 422
    if err in ("invalid_specialty", "invalid_document_type", "invalid_city", "invalid_zone", "invalid_department", "invalid_municipality", "municipality_not_in_department", "invalid_coverage", "coverage_required", "too_many_coverages", "multiple_primary", "duplicate_coverage", "missing_fields", "missing_document"):
        return jsonify({"error": err}), 422
    if not profile:
        return jsonify({"error": "could not update"}), 400
    return jsonify(_profile_to_dict(profile)), 200


@blueprint.patch("/technicians/<int:tid>/availability")
@require_auth
def patch_availability(tid):
    roles = request.user_roles
    if "admin" not in roles and "dispatcher" not in roles:
        # technician can update own
        p = service.get_technician(tid)
        if not p or p.user_id != request.user_id:
            return jsonify({"error": "insufficient permissions"}), 403
    data = request.get_json() or {}
    value = data.get("is_available")
    if value is None:
        return jsonify({"error": "is_available required"}), 422
    profile, err = service.set_availability(tid, bool(value), request.user_id)
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    return jsonify(_profile_to_dict(profile)), 200


@blueprint.post("/technicians/<int:tid>/deactivate")
@require_role("admin")
def deactivate(tid):
    data = request.get_json() or {}
    profile, err = service.deactivate_technician(tid, request.user_id, data.get("reason"))
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "open_orders":
        return jsonify({"error": "open orders exist"}), 409
    return jsonify(_profile_to_dict(profile)), 200


@blueprint.post("/technicians/<int:tid>/activate")
@require_role("admin")
def activate(tid):
    profile, err = service.activate_technician(tid, request.user_id)
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    return jsonify(_profile_to_dict(profile)), 200


@blueprint.post("/technicians/<int:tid>/reset-password")
@require_role("admin")
def reset_password(tid):
    password, username = service.reset_password(tid, request.user_id)
    if not password:
        return jsonify({"error": "not found"}), 404
    return jsonify({"username": username, "temporary_password": password}), 200


@blueprint.post("/technicians/<int:tid>/unlock")
@require_role("admin")
def unlock(tid):
    profile, err = service.unlock_technician(tid, request.user_id)
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    return jsonify(_profile_to_dict(profile)), 200
