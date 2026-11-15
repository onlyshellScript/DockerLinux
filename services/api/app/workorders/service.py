from datetime import datetime, timezone



from app.extensions import db

from app.identity.models import User

from app.workorders.models import (

    WorkOrder,

    WorkOrderStatusHistory,

    TRANSITIONS,

    STATUS_ASSIGNED,

    STATUS_PENDING,

    ALL_STATUSES,

)





def _parse_dt(value):

    if not value:

        return None

    try:

        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    except ValueError:

        return None





def create_work_order(data, created_by_id):

    wo = WorkOrder(

        title=data["title"],

        description=data.get("description"),

        priority=data.get("priority", "medium"),

        customer_name=data.get("customer_name"),

        customer_phone=data.get("customer_phone"),

        address=data.get("address"),

    zone=data.get("zone"),

    legacy_zone=data.get("legacy_zone") or data.get("zone"),

    city_id=data.get("city_id"),

    zone_id=data.get("zone_id"),

    installation_type=data.get("installation_type"),

    installation_type_code=data.get("installation_type_code") or data.get("installation_type"),

        scheduled_at=_parse_dt(data.get("scheduled_at")),

        created_by_id=created_by_id,

    )

    if data.get("assigned_to_id"):

        user = db.session.get(User, data["assigned_to_id"])

        if not user:

            return None

        wo.assigned_to_id = user.id

        wo.status = STATUS_ASSIGNED

    db.session.add(wo)

    db.session.flush()

    db.session.add(WorkOrderStatusHistory(

        work_order_id=wo.id,

        from_status="",

        to_status=wo.status,

        changed_by_id=created_by_id,

        notes="Orden creada",

    ))

    db.session.commit()

    return wo





def list_work_orders(

    status=None,

    assigned_to_id=None,

    q=None,

    zone=None,

    city_id=None,

    zone_id=None,

    priority=None,

    installation_type=None,

    date_from=None,

    date_to=None,

    unassigned=False,

    sort="created_at",

    order="desc",

    page=1,

    page_size=10,

    for_user_id=None,

    for_user_roles=None,

):

    query = WorkOrder.query



    # technician scoping

    roles = for_user_roles or []

    if for_user_id and "admin" not in roles and "dispatcher" not in roles:

        query = query.filter(WorkOrder.assigned_to_id == for_user_id)



    if status:

        query = query.filter(WorkOrder.status == status)

    if assigned_to_id:

        query = query.filter(WorkOrder.assigned_to_id == assigned_to_id)

    if unassigned:

        query = query.filter(WorkOrder.assigned_to_id.is_(None))

    if zone:

        query = query.filter(WorkOrder.zone == zone)

    if city_id:

        query = query.filter(WorkOrder.city_id == int(city_id))

    if zone_id:

        query = query.filter(WorkOrder.zone_id == int(zone_id))

    if priority:

        query = query.filter(WorkOrder.priority == priority)

    if installation_type:

        query = query.filter(WorkOrder.installation_type == installation_type)

    if date_from:

        df = _parse_dt(date_from)

        if df:

            query = query.filter(WorkOrder.scheduled_at >= df)

    if date_to:

        dt = _parse_dt(date_to)

        if dt:

            query = query.filter(WorkOrder.scheduled_at <= dt)

    if q:

        like = f"%{q}%"

        query = query.filter(

            db.or_(

                WorkOrder.title.ilike(like),

                WorkOrder.customer_name.ilike(like),

                WorkOrder.address.ilike(like),

                db.cast(WorkOrder.id, db.String).ilike(like),

            )

        )



    # counts by status (respecting filters except status)

    count_query = WorkOrder.query

    if for_user_id and "admin" not in roles and "dispatcher" not in roles:

        count_query = count_query.filter(WorkOrder.assigned_to_id == for_user_id)

    if q:

        like = f"%{q}%"

        count_query = count_query.filter(

            db.or_(

                WorkOrder.title.ilike(like),

                WorkOrder.customer_name.ilike(like),

                WorkOrder.address.ilike(like),

                db.cast(WorkOrder.id, db.String).ilike(like),

            )

        )

    if zone:

        count_query = count_query.filter(WorkOrder.zone == zone)

    if city_id:

        count_query = count_query.filter(WorkOrder.city_id == int(city_id))

    if zone_id:

        count_query = count_query.filter(WorkOrder.zone_id == int(zone_id))

    if priority:

        count_query = count_query.filter(WorkOrder.priority == priority)

    if installation_type:

        count_query = count_query.filter(WorkOrder.installation_type == installation_type)

    if assigned_to_id:

        count_query = count_query.filter(WorkOrder.assigned_to_id == assigned_to_id)

    if unassigned:

        count_query = count_query.filter(WorkOrder.assigned_to_id.is_(None))

    counts = {}

    for st in ALL_STATUSES:

        counts[st] = count_query.filter(WorkOrder.status == st).count()



    # sorting

    sort_col = {

        "id": WorkOrder.id,

        "customer": WorkOrder.customer_name,

        "scheduled_at": WorkOrder.scheduled_at,

        "status": WorkOrder.status,

        "priority": WorkOrder.priority,

        "created_at": WorkOrder.created_at,

    }.get(sort, WorkOrder.created_at)

    if order == "asc":

        query = query.order_by(sort_col.asc())

    else:

        query = query.order_by(sort_col.desc())



    total = query.count()

    page = max(1, int(page or 1))

    page_size = max(1, min(100, int(page_size or 10)))

    items = query.offset((page - 1) * page_size).limit(page_size).all()



    return {

        "items": items,

        "total": total,

        "page": page,

        "page_size": page_size,

        "counts": counts,

    }





def get_work_order(wo_id):

    return db.session.get(WorkOrder, wo_id)





def update_work_order(wo_id, data, changed_by_id):

    wo = db.session.get(WorkOrder, wo_id)

    if not wo:

        return None

    for field in ("title", "description", "priority", "customer_name", "customer_phone", "address", "zone", "legacy_zone", "city_id", "zone_id", "installation_type", "installation_type_code", "cancel_reason"):

        if field in data:

            setattr(wo, field, data[field])

    if "assigned_to_id" in data:

        if data["assigned_to_id"]:

            user = db.session.get(User, data["assigned_to_id"])

            if not user:

                return None

            wo.assigned_to_id = user.id

        else:

            wo.assigned_to_id = None

    if "scheduled_at" in data:

        wo.scheduled_at = _parse_dt(data["scheduled_at"])

    db.session.commit()

    return wo





def change_status(wo_id, to_status, user, notes=None, reason=None, technician_id=None, scheduled_at=None):

    wo = db.session.get(WorkOrder, wo_id)

    if not wo:

        return None, "not_found"

    allowed = TRANSITIONS.get(wo.status, set())

    if to_status not in allowed:

        return None, "invalid_transition"

    if to_status == "cancelled" and not reason:

        return None, "reason_required"

    from_status = wo.status

    wo.status = to_status

    if technician_id:

        u = db.session.get(User, technician_id)

        if not u:

            return None, "not_found"

        wo.assigned_to_id = u.id

    if scheduled_at:

        wo.scheduled_at = _parse_dt(scheduled_at)

    if to_status == "completed" and wo.completed_at is None:

        wo.completed_at = datetime.now(timezone.utc)

    if to_status == "cancelled":

        wo.cancel_reason = reason

    db.session.add(WorkOrderStatusHistory(

        work_order_id=wo.id,

        from_status=from_status,

        to_status=to_status,

        changed_by_id=user.id,

        notes=notes or reason,

    ))

    from app.settings.models import AuditLog

    db.session.add(AuditLog(

        user_id=user.id,

        section="OrdenesTrabajo",

        field="Estado",

        old_value=from_status,

        new_value=to_status,

        result="applied",

        username=user.username,

    ))

    roles = [r.name for r in (user.roles or [])]

    if "technician" in roles:

        from app.notifications.service import notify_technician_change

        notify_technician_change(wo, user, "estado " + from_status + " -> " + to_status)

    db.session.commit()

    return wo, None





def transition_work_order(wo_id, action, user, technician_id=None, scheduled_at=None, reason=None, notes=None):

    wo = db.session.get(WorkOrder, wo_id)

    if not wo:

        return None, "not_found"

    action_map = {
        "assign": "assigned",
        "start": "in_progress",
        "complete": "completed",
        "cancel": "cancelled",
    }
    to_status = action_map.get(action)

    if not to_status:

        return None, "invalid_action"

    allowed = TRANSITIONS.get(wo.status, set())

    if to_status not in allowed:

        return None, "invalid_transition"

    from_status = wo.status

    wo.status = to_status

    if technician_id:

        u = db.session.get(User, technician_id)

        if not u:

            return None, "not_found"

        wo.assigned_to_id = u.id

    if scheduled_at:

        wo.scheduled_at = _parse_dt(scheduled_at)

    if to_status == "completed" and wo.completed_at is None:

        wo.completed_at = datetime.now(timezone.utc)

    if to_status == "cancelled":

        wo.cancel_reason = reason

    db.session.add(WorkOrderStatusHistory(

        work_order_id=wo.id,

        from_status=from_status,

        to_status=to_status,

        changed_by_id=user.id,

        notes=notes or reason,

    ))

    from app.settings.models import AuditLog

    db.session.add(AuditLog(

        user_id=user.id,

        section="OrdenesTrabajo",

        field="Estado",

        old_value=from_status,

        new_value=to_status,

        result="applied",

        username=user.username,

    ))

    roles = [r.name for r in (user.roles or [])]

    if "technician" in roles:

        from app.notifications.service import notify_technician_change

        notify_technician_change(wo, user, "estado " + from_status + " -> " + to_status)

    db.session.commit()

    return wo, None





def record_used_materials(wo_id, user, items):
    from app.materials.models import Material, StockMovement
    from app.notifications.service import notify_technician_change
    wo = db.session.get(WorkOrder, wo_id)
    if not wo:
        return None, "not_found"
    roles = [r.name for r in (user.roles or [])]
    is_technician = "technician" in roles
    is_dispatcher = "dispatcher" in roles
    if not (is_technician or is_dispatcher):
        return None, "forbidden"
    if is_technician and wo.assigned_to_id != user.id:
        return None, "forbidden"
    details = []
    for it in items or []:
        mid = it.get("material_id")
        qty = float(it.get("quantity", 0))
        if not mid or qty <= 0:
            continue
        mat = db.session.get(Material, mid)
        if not mat:
            return None, "invalid_material"
        if (mat.current_stock or 0) < qty:
            return None, "insufficient_stock"
        mat.current_stock = (mat.current_stock or 0) - qty
        mv = StockMovement(
            material_id=mid,
            quantity=qty,
            quantity_requested=qty,
            quantity_approved=qty,
            quantity_delivered=qty,
            movement_type="CONSUMPTION",
            work_order_id=wo.id,
            user_id=user.id,
            notes="Consumo en orden %d" % wo.id,
        )
        db.session.add(mv)
        details.append("%s x%s" % (mat.name, qty))
    if not details:
        return wo, None
    from app.settings.models import AuditLog
    db.session.add(AuditLog(
        user_id=user.id,
        section="OrdenesTrabajo",
        field="Materiales",
        old_value=None,
        new_value=", ".join(details),
        result="applied",
        username=user.username,
    ))
    if is_technician:
        notify_technician_change(wo, user, "materiales: " + ", ".join(details))
    db.session.commit()
    return wo, None


def get_history(wo_id):

    return WorkOrderStatusHistory.query.filter_by(work_order_id=wo_id).order_by(WorkOrderStatusHistory.created_at).all()





def bulk_update(ids, action, payload, user_id, user_roles):

    results = []

    for oid in ids:

        try:

            if action == "assign":

                wo = update_work_order(oid, {"assigned_to_id": payload.get("technician_id")}, user_id)

                if wo and payload.get("scheduled_at"):

                    wo.scheduled_at = _parse_dt(payload.get("scheduled_at"))

                    if wo.status == "pending":

                        wo.status = "assigned"

                    db.session.commit()

                results.append({"id": oid, "ok": True})

            elif action == "priority":

                wo = update_work_order(oid, {"priority": payload.get("priority")}, user_id)

                results.append({"id": oid, "ok": bool(wo)})

            elif action == "cancel":

                wo, err = transition_work_order(oid, "cancel", db.session.get(User, user_id), reason=payload.get("reason"))

                results.append({"id": oid, "ok": wo is not None, "error": err})

            else:

                results.append({"id": oid, "ok": False, "error": "unknown_action"})

        except Exception as e:

            results.append({"id": oid, "ok": False, "error": str(e)})

    return results





def export_csv(query_result):

    import csv, io

    buf = io.StringIO()

    writer = csv.writer(buf)

    writer.writerow(["ID", "Cliente", "Dirección", "Zona", "Tipo", "Técnico", "Fecha visita", "Estado", "Prioridad"])

    for wo in query_result:

        writer.writerow([

            f"OS-{wo.id:04d}",

            wo.customer_name or "",

            wo.address or "",

            wo.zone or "",

            wo.installation_type or "",

            wo.assigned_to.username if wo.assigned_to else "",

            wo.scheduled_at.strftime("%d/%m/%Y %H:%M") if wo.scheduled_at else "",

            wo.status,

            wo.priority,

        ])

    return buf.getvalue()

