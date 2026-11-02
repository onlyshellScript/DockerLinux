from flask import Blueprint, request, jsonify

from app.extensions import db
from app.identity.decorators import require_auth, require_role
from app.identity.models import User, Role, AuditEvent
from app.settings import service
from app.settings.models import AuditLog

blueprint = Blueprint("settings", __name__)


def _is_admin(roles):
    return "admin" in roles


@blueprint.get("/settings/organization")
@require_auth
def get_org():
    roles = request.user_roles
    if "admin" not in roles and "dispatcher" not in roles:
        return jsonify({"error": "forbidden"}), 403
    row = service.get_organization()
    return jsonify({
        "company_name": row.company_name,
        "nit": row.nit,
        "admin_email": row.admin_email,
        "contact_phone": row.contact_phone,
        "address": row.address,
        "city_id": row.city_id,
        "timezone": row.timezone,
        "version": row.version,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }), 200


@blueprint.patch("/settings/organization")
@require_role("admin")
def patch_org():
    data = request.get_json() or {}
    user = db.session.get(User, request.user_id)
    roles = request.user_roles
    row, err = service.patch_organization(data, request.user_id)
    if err == "stale_version":
        return jsonify({"error": "stale version", "code": "STALE_VERSION"}), 409
    if err == "invalid_timezone":
        return jsonify({"error": "invalid timezone", "field": "timezone"}), 422
    if err == "invalid_city":
        return jsonify({"error": "invalid city", "field": "city_id"}), 422
    if err == "unknown_field":
        return jsonify({"error": "unknown field"}), 422
    if not row:
        return jsonify({"error": "could not update"}), 400
    # audit
    service.audit(request.user_id, user.username if user else None, "organization", None, None, None, "applied", request.headers.get("X-Request-Id"))
    db.session.commit()
    return jsonify({"version": row.version, "message": "Cambios guardados correctamente."}), 200


@blueprint.get("/settings/operations")
@require_auth
def get_ops():
    roles = request.user_roles
    if "admin" not in roles and "dispatcher" not in roles:
        return jsonify({"error": "forbidden"}), 403
    return jsonify(service.operational_dict()), 200


@blueprint.patch("/settings/operations")
@require_role("admin")
def patch_ops():
    data = request.get_json() or {}
    user = db.session.get(User, request.user_id)
    row, err = service.patch_operations(data, request.user_id)
    if err == "stale_version":
        return jsonify({"error": "stale version", "code": "STALE_VERSION"}), 409
    if err in ("invalid_range", "invalid_value"):
        return jsonify({"error": err}), 422
    if err == "unknown_field":
        return jsonify({"error": "unknown field"}), 422
    if not row:
        return jsonify({"error": "could not update"}), 400
    service.audit(request.user_id, user.username if user else None, "operations", None, None, None, "applied", request.headers.get("X-Request-Id"))
    db.session.commit()
    return jsonify({"version": row.version, "message": "Cambios guardados correctamente."}), 200


@blueprint.post("/settings/operations/impact")
@require_role("admin")
def ops_impact():
    data = request.get_json() or {}
    result = service.operations_impact(data)
    return jsonify(result), 200


@blueprint.get("/settings/security")
@require_role("admin")
def get_sec():
    row = service.get_security()
    return jsonify({
        "session_inactivity_minutes": row.session_inactivity_minutes,
        "session_max_hours": row.session_max_hours,
        "password_min_length": row.password_min_length,
        "password_history_count": row.password_history_count,
        "lock_attempts": row.lock_attempts,
        "lock_minutes": row.lock_minutes,
        "temp_password_validity_days": row.temp_password_validity_days,
        "version": row.version,
    }), 200


@blueprint.patch("/settings/security")
@require_role("admin")
def patch_sec():
    data = request.get_json() or {}
    user = db.session.get(User, request.user_id)
    row, err = service.patch_security(data, request.user_id)
    if err == "stale_version":
        return jsonify({"error": "stale version", "code": "STALE_VERSION"}), 409
    if err == "unknown_field":
        return jsonify({"error": "unknown field"}), 422
    if not row:
        return jsonify({"error": "could not update"}), 400
    service.audit(request.user_id, user.username if user else None, "security", None, None, None, "applied", request.headers.get("X-Request-Id"))
    db.session.commit()
    return jsonify({"version": row.version, "message": "Cambios guardados correctamente."}), 200


@blueprint.get("/settings/notifications")
@require_auth
def get_notif():
    roles = request.user_roles
    if "admin" not in roles and "dispatcher" not in roles:
        return jsonify({"error": "forbidden"}), 403
    row = service.get_notifications()
    return jsonify({"preferences": row.preferences, "version": row.version}), 200


@blueprint.patch("/settings/notifications")
@require_role("admin")
def patch_notif():
    data = request.get_json() or {}
    user = db.session.get(User, request.user_id)
    row, err = service.patch_notifications(data, request.user_id, user_scope=False)
    if err == "stale_version":
        return jsonify({"error": "stale version", "code": "STALE_VERSION"}), 409
    if err in ("invalid_value", "unknown_field"):
        return jsonify({"error": err}), 422
    if not row:
        return jsonify({"error": "could not update"}), 400
    service.audit(request.user_id, user.username if user else None, "notifications", None, None, None, "applied", request.headers.get("X-Request-Id"))
    db.session.commit()
    return jsonify({"version": row.version, "message": "Cambios guardados correctamente."}), 200


@blueprint.get("/settings/notifications/me")
@require_auth
def get_notif_me():
    row = service.get_user_notifications(request.user_id)
    return jsonify({"preferences": row.preferences, "version": row.version}), 200


@blueprint.patch("/settings/notifications/me")
@require_auth
def patch_notif_me():
    data = request.get_json() or {}
    row, err = service.patch_notifications(data, request.user_id, user_scope=True)
    if err == "stale_version":
        return jsonify({"error": "stale version", "code": "STALE_VERSION"}), 409
    if err in ("invalid_value", "unknown_field"):
        return jsonify({"error": err}), 422
    if not row:
        return jsonify({"error": "could not update"}), 400
    return jsonify({"version": row.version, "message": "Cambios guardados correctamente."}), 200


@blueprint.get("/settings/public")
@require_auth
def public():
    return jsonify(service.public_settings()), 200


@blueprint.get("/audit-log")
@require_role("admin")
def audit_list():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    section = request.args.get("section")
    user_id = request.args.get("user_id", type=int)
    result = request.args.get("result")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    q = AuditLog.query
    if section:
        q = q.filter(AuditLog.section == section)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if result:
        q = q.filter(AuditLog.result == result)
    if date_from:
        try:
            from datetime import datetime
            df = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
            q = q.filter(AuditLog.created_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            q = q.filter(AuditLog.created_at <= dt)
        except ValueError:
            pass
    total = q.count()
    items = q.order_by(AuditLog.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return jsonify({
        "items": [{
            "id": a.id,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "user_id": a.user_id,
            "username": a.username,
            "section": a.section,
            "field": a.field,
            "old_value": a.old_value,
            "new_value": a.new_value,
            "result": a.result,
        } for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }), 200


@blueprint.get("/audit-log/export.csv")
@require_role("admin")
def audit_export():
    import csv, io
    # reuse filters
    section = request.args.get("section")
    user_id = request.args.get("user_id", type=int)
    result = request.args.get("result")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    q = AuditLog.query
    if section:
        q = q.filter(AuditLog.section == section)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if result:
        q = q.filter(AuditLog.result == result)
    if date_from:
        try:
            from datetime import datetime
            df = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
            q = q.filter(AuditLog.created_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            q = q.filter(AuditLog.created_at <= dt)
        except ValueError:
            pass
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["fecha", "usuario", "seccion", "campo", "anterior", "nuevo", "resultado"])
    for a in q.order_by(AuditLog.created_at.desc()).all():
        w.writerow([a.created_at.isoformat() if a.created_at else "", a.username or "", a.section, a.field or "", a.old_value or "", a.new_value or "", a.result])
    return buf.getvalue(), 200, {"Content-Type": "text/csv"}
