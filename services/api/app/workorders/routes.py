from flask import Blueprint, request, jsonify, Response
from app.extensions import db
from app.identity.decorators import require_auth, require_role
from app.identity.models import User
from app.workorders.models import ALL_STATUSES
from app.workorders.service import (
    create_work_order,
    list_work_orders,
    get_work_order,
    update_work_order,
    change_status,
    transition_work_order,
    get_history,
    bulk_update,
    export_csv,
    record_used_materials,
)
from app.calendar import service as calendar_service

blueprint = Blueprint("workorders", __name__)


@blueprint.get("/work-orders")
@require_auth
def work_orders_list():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 10, type=int)
    sort = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc")
    status = request.args.get("status")
    zone = request.args.get("zone")
    city_id = request.args.get("city_id")
    zone_id = request.args.get("zone_id")
    priority = request.args.get("priority")
    itype = request.args.get("type")
    q = request.args.get("q")
    technician_id = request.args.get("technician_id", type=int)
    unassigned = request.args.get("unassigned", "false").lower() == "true"
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    roles = request.user_roles
    result = list_work_orders(
        status=status,
        assigned_to_id=technician_id,
        q=q,
        zone=zone,
        city_id=city_id,
        zone_id=zone_id,
        priority=priority,
        installation_type=itype,
        date_from=date_from,
        date_to=date_to,
        unassigned=unassigned,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
        for_user_id=request.user_id,
        for_user_roles=roles,
    )
    items = [o.to_dict() for o in result["items"]]
    return jsonify({
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "counts": result["counts"],
    }), 200


@blueprint.post("/work-orders")
@require_role("dispatcher")
def work_orders_create():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "title required"}), 400
    wo = create_work_order(data, request.user_id)
    if not wo:
        return jsonify({"error": "invalid assigned_to_id"}), 400
    return jsonify(wo.to_dict()), 201


@blueprint.get("/work-orders/<int:wo_id>")
@require_auth
def work_orders_get(wo_id):
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "work order not found"}), 404
    # technician scoping
    roles = request.user_roles
    if "admin" not in roles and "dispatcher" not in roles and wo.assigned_to_id != request.user_id:
        return jsonify({"error": "insufficient permissions"}), 403
    return jsonify(wo.to_dict()), 200


@blueprint.patch("/work-orders/<int:wo_id>")
@require_auth
def work_orders_patch(wo_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "work order not found"}), 404
    roles = request.user_roles
    is_admin = "admin" in roles
    is_dispatcher = "dispatcher" in roles
    if not (is_admin or is_dispatcher):
        return jsonify({"error": "insufficient permissions"}), 403
    if_match = request.headers.get("If-Match")
    if if_match:
        try:
            ifm = int(if_match.strip().strip('"'))
        except ValueError:
            return jsonify({"error": "invalid If-Match version"}), 400
        if ifm != wo.version:
            return jsonify({"error": "stale version"}), 400
    if is_admin and wo.status in ("completed", "cancelled"):
        return jsonify({"error": "cannot edit terminal order"}), 409
    if is_admin:
        reason = data.get("reason")
        if not reason:
            return jsonify({"error": "reason required"}), 422
        if "status" in data and data.get("status") == "cancelled":
            return jsonify({"error": "admin cannot cancel orders"}), 403
    if is_dispatcher and wo.assigned_to_id != request.user_id and "dispatcher" not in roles:
        pass

    old_assigned = wo.assigned_to_id
    old_scheduled = wo.scheduled_at
    old_title = wo.title

    tracked = ("title", "description", "priority", "customer_name", "customer_phone", "address", "zone", "legacy_zone", "city_id", "zone_id", "installation_type", "installation_type_code", "assigned_to_id", "scheduled_at", "scheduled_end")
    old_values = {}
    for f in tracked:
        if f in data:
            v = getattr(wo, f, None)
            if hasattr(v, "isoformat"):
                v = v.isoformat() if v is not None else None
            old_values[f] = v

    # Validación de programación (solape, horario, domingos) si se envía fecha
    if "scheduled_at" in data or "scheduled_end" in data or "scheduled_end" in data:
        from app.calendar import service as calendar_service
        v_roles = roles if "dispatcher" in roles else (roles + ["dispatcher"])
        vresult, verr = calendar_service.validate_schedule(wo_id, data, v_roles)
        if verr == "forbidden":
            return jsonify({"error": "forbidden"}), 403
        if verr == "not_found":
            return jsonify({"error": "not found"}), 404
        if verr:
            return jsonify({"error": verr}), 400
        if not vresult.get("ok", True):
            conflicts = vresult.get("conflicts") or []
            code = conflicts[0].get("code") if conflicts else "schedule_conflict"
            return jsonify({"error": code, "conflicts": conflicts}), 409

    wo = update_work_order(wo_id, data, request.user_id)
    if not wo:
        return jsonify({"error": "work order not found"}), 404

    if is_admin:
        actor = db.session.get(__import__("app.identity.models", fromlist=["User"]).User, request.user_id)
        actor_name = actor.username if actor else None
        reason = data.get("reason")
        from app.settings.models import AuditLog
        # Audit per changed field (additive; legacy generic entries remain readable).
        for f in tracked:
            if f not in data:
                continue
            new_val = data.get(f)
            if hasattr(new_val, "isoformat"):
                new_val = new_val.isoformat() if new_val is not None else None
            old_val = old_values.get(f)
            if str(old_val) == str(new_val):
                continue
            db.session.add(AuditLog(
                user_id=request.user_id,
                section="OrdenesTrabajo",
                field=f"work_order:{wo_id}:{f}",
                old_value=None if old_val is None else str(old_val),
                new_value=None if new_val is None else str(new_val),
                result="applied",
                request_id=(str(reason)[:40] if reason is not None else None),
                username=actor_name,
            ))
        db.session.commit()

    # notify technician on reassignment or reschedule
    try:
        from app.notifications.service import create_in_app_notification
        if wo.assigned_to_id and (wo.assigned_to_id != old_assigned or wo.scheduled_at != old_scheduled):
            create_in_app_notification(
                wo.assigned_to_id,
                f"Cambio en orden OS-{wo.id:04d}",
                f"La orden OS-{wo.id:04d} fue modificada por un administrador.",
            )
            db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify(wo.to_dict()), 200


@blueprint.put("/work-orders/<int:wo_id>")
@require_role("dispatcher")
def work_orders_update(wo_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400
    if "assigned_to_id" in data and data["assigned_to_id"]:
        user = db.session.get(User, data["assigned_to_id"])
        if not user:
            return jsonify({"error": "assigned user not found"}), 400
    wo = update_work_order(wo_id, data, request.user_id)
    if not wo:
        return jsonify({"error": "work order not found"}), 404
    return jsonify(wo.to_dict()), 200


@blueprint.post("/work-orders/<int:wo_id>/status")
@require_auth
def work_orders_change_status(wo_id):
    data = request.get_json()
    if not data or not data.get("to_status"):
        return jsonify({"error": "to_status required"}), 400
    to_status = data["to_status"]
    if to_status not in ALL_STATUSES:
        return jsonify({"error": "invalid status"}), 400

    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "work order not found"}), 404
    roles = request.user_roles
    is_admin = False  # admin cannot change status
    is_dispatcher = "dispatcher" in roles
    is_assigned = wo.assigned_to_id == request.user_id
    if to_status in ("assigned", "in_progress", "completed") and not (is_dispatcher or is_assigned):
        return jsonify({"error": "insufficient permissions"}), 403
    if to_status == "cancelled" and not is_dispatcher:
        return jsonify({"error": "insufficient permissions"}), 403

    user = db.session.get(__import__("app.identity.models", fromlist=["User"]).User, request.user_id)
    result, error = change_status(wo_id, to_status, user, data.get("notes"), data.get("reason"), data.get("technician_id"), data.get("scheduled_at"))
    if error == "not_found":
        return jsonify({"error": "work order not found"}), 404
    if error == "invalid_transition":
        return jsonify({"error": f"cannot transition from {wo.status} to {to_status}"}), 409
    if error == "reason_required":
        return jsonify({"error": "reason required"}), 422
    return jsonify(result.to_dict()), 200


@blueprint.post("/work-orders/<int:wo_id>/transitions")
@require_auth
def work_orders_transition(wo_id):
    data = request.get_json() or {}
    action = data.get("action")
    if not action:
        return jsonify({"error": "action required"}), 400
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "work order not found"}), 404
    roles = request.user_roles
    is_admin = False  # admin cannot manage orders
    is_dispatcher = "dispatcher" in roles
    is_assigned = wo.assigned_to_id == request.user_id
    # permission checks by action
    if action in ("assign", "cancel") and not is_dispatcher:
        return jsonify({"error": "insufficient permissions"}), 403
    if action in ("start", "complete") and not (is_dispatcher or is_assigned):
        return jsonify({"error": "insufficient permissions"}), 403
    if action == "cancel" and not data.get("reason"):
        return jsonify({"error": "reason required"}), 422
    if action == "complete" and not data.get("notes"):
        return jsonify({"error": "notes required"}), 422
    if action == "assign" and (not data.get("technician_id") or not data.get("scheduled_at")):
        return jsonify({"error": "technician_id and scheduled_at required"}), 422

    user = db.session.get(__import__("app.identity.models", fromlist=["User"]).User, request.user_id)
    result, error = transition_work_order(
        wo_id, action, user,
        technician_id=data.get("technician_id"),
        scheduled_at=data.get("scheduled_at"),
        reason=data.get("reason"),
        notes=data.get("notes"),
    )
    if error == "not_found":
        return jsonify({"error": "work order not found"}), 404
    if error in ("invalid_transition", "invalid_action"):
        return jsonify({"error": f"cannot perform {action}"}), 409
    return jsonify(result.to_dict()), 200


@blueprint.post("/work-orders/<int:wo_id>/schedule")
@require_auth
def work_orders_schedule(wo_id):
    data = request.get_json() or {}
    if "version" not in data and request.headers.get("If-Match"):
        try:
            data["version"] = int(request.headers.get("If-Match").strip().strip('\"'))
        except ValueError:
            return jsonify({"error": "invalid If-Match version"}), 400
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "not found"}), 404
    roles = request.user_roles
    if "dispatcher" not in roles and "admin" not in roles:
        return jsonify({"error": "forbidden"}), 403
    result, err = calendar_service.schedule_order(wo_id, data, db.session.get(__import__("app.identity.models", fromlist=["User"]).User, request.user_id), roles)
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err == "sunday_authorization_required":
        try:
            from app.notifications.service import create_in_app_notification
            from app.identity.models import User, Role
            admins = User.query.join(User.roles).filter(Role.name == "admin").all()
            for a in admins:
                create_in_app_notification(a.id, "Autorización domingo/festivo", "Se requiere autorización para programar en domingo o festivo.")
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"error": "sunday authorization required", "code": "sunday_authorization_required"}), 403
    if err == "reason_required":
        return jsonify({"error": "reason required"}), 422
    if err == "stale_version":
        return jsonify({"error": "stale version", "code": "STALE_VERSION"}), 409
    if err == "invalid_transition":
        return jsonify({"error": "invalid transition", "code": "INVALID_TRANSITION"}), 409
    if err == "reason_required":
        return jsonify({"error": "reason required"}), 422
    if err == "invalid_time":
        return jsonify({"error": "invalid time"}), 422
    if err == "duration_too_long":
        return jsonify({"error": "duration too long"}), 422
    if err == "invalid_technician":
        return jsonify({"error": "invalid technician"}), 422
    if err == "schedule_conflict":
        return jsonify({"error": "schedule conflict", "code": "SCHEDULE_CONFLICT"}), 409
    if not result:
        return jsonify({"error": "could not schedule"}), 400
    return jsonify(result.to_dict()), 200


@blueprint.patch("/work-orders/<int:wo_id>/schedule")
@require_auth
def work_orders_reschedule(wo_id):
    data = request.get_json() or {}
    data = dict(data)
    if "version" not in data and request.headers.get("If-Match"):
        try:
            data["version"] = int(request.headers.get("If-Match").strip().strip('\"'))
        except ValueError:
            return jsonify({"error": "invalid If-Match version"}), 400
    data.setdefault("reason", data.get("reason") or data.get("motivo"))
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "not found"}), 404
    roles = request.user_roles
    if "dispatcher" not in roles and "admin" not in roles:
        return jsonify({"error": "forbidden"}), 403
    result, err = calendar_service.schedule_order(wo_id, data, db.session.get(__import__("app.identity.models", fromlist=["User"]).User, request.user_id), roles)
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err == "sunday_authorization_required":
        try:
            from app.notifications.service import create_in_app_notification
            from app.identity.models import User, Role
            admins = User.query.join(User.roles).filter(Role.name == "admin").all()
            for a in admins:
                create_in_app_notification(a.id, "Autorización domingo/festivo", "Se requiere autorización para programar en domingo o festivo.")
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"error": "sunday authorization required", "code": "sunday_authorization_required"}), 403
    if err == "reason_required":
        return jsonify({"error": "reason required"}), 422
    if err == "stale_version":
        return jsonify({"error": "stale version", "code": "STALE_VERSION"}), 409
    if err == "invalid_transition":
        return jsonify({"error": "invalid transition", "code": "INVALID_TRANSITION"}), 409
    if err == "reason_required":
        return jsonify({"error": "reason required"}), 422
    if err == "invalid_time":
        return jsonify({"error": "invalid time"}), 422
    if err == "duration_too_long":
        return jsonify({"error": "duration too long"}), 422
    if err == "invalid_technician":
        return jsonify({"error": "invalid technician"}), 422
    if err == "schedule_conflict":
        return jsonify({"error": "schedule conflict", "code": "SCHEDULE_CONFLICT"}), 409
    if not result:
        return jsonify({"error": "could not schedule"}), 400
    return jsonify(result.to_dict()), 200


@blueprint.post("/work-orders/<int:wo_id>/assignments")
@require_auth
def work_orders_assign(wo_id):
    data = request.get_json() or {}
    roles = request.user_roles
    if "dispatcher" not in roles and "admin" not in roles:
        return jsonify({"error": "forbidden"}), 403
    result, err = calendar_service.assign_order(wo_id, data, db.session.get(__import__("app.identity.models", fromlist=["User"]).User, request.user_id), roles)
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err == "sunday_authorization_required":
        try:
            from app.notifications.service import create_in_app_notification
            from app.identity.models import User, Role
            admins = User.query.join(User.roles).filter(Role.name == "admin").all()
            for a in admins:
                create_in_app_notification(a.id, "Autorización domingo/festivo", "Se requiere autorización para programar en domingo o festivo.")
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"error": "sunday authorization required", "code": "sunday_authorization_required"}), 403
    if err == "reason_required":
        return jsonify({"error": "reason required"}), 422
    if err == "invalid_transition":
        return jsonify({"error": "invalid transition", "code": "INVALID_TRANSITION"}), 409
    if err == "invalid_technician":
        return jsonify({"error": "invalid technician"}), 422
    if err == "schedule_conflict":
        return jsonify({"error": "schedule conflict", "code": "SCHEDULE_CONFLICT"}), 409
    if not result:
        return jsonify({"error": "could not assign"}), 400
    return jsonify(result.to_dict()), 200


@blueprint.post("/work-orders/<int:wo_id>/materials")
@require_auth
def work_orders_materials(wo_id):
    roles = request.user_roles
    if "admin" in roles and "dispatcher" not in roles:
        return jsonify({"error": "insufficient permissions"}), 403
    data = request.get_json() or {}
    items = data.get("items") or data.get("materials") or []
    if not items:
        return jsonify({"error": "items required"}), 400
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "work order not found"}), 404
    user = db.session.get(__import__("app.identity.models", fromlist=["User"]).User, request.user_id)
    is_technician = "technician" in roles
    if is_technician and wo.assigned_to_id != request.user_id:
        return jsonify({"error": "insufficient permissions"}), 403
    result, error = record_used_materials(wo_id, user, items)
    if error == "not_found":
        return jsonify({"error": "work order not found"}), 404
    if error == "forbidden":
        return jsonify({"error": "insufficient permissions"}), 403
    if error == "invalid_material":
        return jsonify({"error": "invalid material"}), 400
    return jsonify(result.to_dict()), 200


@blueprint.get("/work-orders/<int:wo_id>/history")
@require_auth
def work_orders_history(wo_id):
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "work order not found"}), 404
    roles = request.user_roles
    if "admin" not in roles and "dispatcher" not in roles and wo.assigned_to_id != request.user_id:
        return jsonify({"error": "insufficient permissions"}), 403
    history = get_history(wo_id)
    return jsonify([h.to_dict() for h in history]), 200


@blueprint.get("/work-orders/<int:wo_id>/timeline")
@require_auth
def work_orders_timeline(wo_id):
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "work order not found"}), 404
    roles = request.user_roles
    if "admin" not in roles and "dispatcher" not in roles and wo.assigned_to_id != request.user_id:
        return jsonify({"error": "insufficient permissions"}), 403
    history = []
    for h in get_history(wo_id):
        d = h.to_dict()
        d.setdefault("field", "status")
        d.setdefault("old_value", d.get("from_status"))
        d.setdefault("new_value", d.get("to_status"))
        d.setdefault("reason", d.get("notes"))
        d.setdefault("actor", (d.get("changed_by") or {}).get("username"))
        history.append(d)
    try:
        from app.settings.models import AuditLog
        audits = AuditLog.query.filter(
            AuditLog.section == "OrdenesTrabajo",
            db.or_(
                AuditLog.field == f"work_order:{wo_id}",
                AuditLog.field.like(f"work_order:{wo_id}:%"),
            ),
        ).order_by(AuditLog.created_at).all()
        for a in audits:
            actor = db.session.get(User, a.user_id) if a.user_id else None
            if actor is None and a.username:
                actor = User.query.filter_by(username=a.username).first()
            # derive field name for per-field entries
            field_name = a.field or ""
            if field_name.startswith(f"work_order:{wo_id}:"):
                field_name = field_name.split(":", 2)[-1] if ":" in field_name else field_name
            elif field_name == f"work_order:{wo_id}":
                field_name = "work_order"
            history.append({
                "id": a.id,
                "work_order_id": wo_id,
                "from_status": None,
                "to_status": None,
                "changed_by": actor.to_dict() if actor else ({"username": a.username} if a.username else None),
                "notes": a.new_value,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "audit": True,
                "field": field_name,
                "old_value": a.old_value,
                "new_value": a.new_value,
                "reason": a.request_id,
                "actor": a.username or (actor.username if actor else None),
            })
    except Exception:
        pass
    history.sort(key=lambda x: x.get("created_at") or "")
    return jsonify(history), 200


@blueprint.post("/work-orders/bulk")
@require_role("dispatcher")
def work_orders_bulk():
    data = request.get_json() or {}
    ids = data.get("ids") or []
    action = data.get("action")
    payload = data.get("payload") or {}
    if not ids or not action:
        return jsonify({"error": "ids and action required"}), 400
    user = db.session.get(__import__("app.identity.models", fromlist=["User"]).User, request.user_id)
    results = bulk_update(ids, action, payload, request.user_id, request.user_roles)
    return jsonify({"results": results}), 200


@blueprint.get("/work-orders/export.csv")
@require_auth
def work_orders_export():
    # reuse list filters
    page = 1
    page_size = 10000
    result = list_work_orders(
        status=request.args.get("status"),
        assigned_to_id=request.args.get("technician_id", type=int),
        q=request.args.get("q"),
        zone=request.args.get("zone"),
        priority=request.args.get("priority"),
        installation_type=request.args.get("type"),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        unassigned=request.args.get("unassigned", "false").lower() == "true",
        sort=request.args.get("sort", "created_at"),
        order=request.args.get("order", "desc"),
        page=page,
        page_size=page_size,
        for_user_id=request.user_id,
        for_user_roles=request.user_roles,
    )
    csv_data = export_csv(result["items"])
    return Response(csv_data, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=ordenes.csv"})
