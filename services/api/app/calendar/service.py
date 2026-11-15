# -*- coding: utf-8 -*-
import threading
from datetime import datetime, timedelta, timezone

from app.extensions import db
from sqlalchemy import or_ as _or
from app.workorders.models import WorkOrder, ALL_STATUSES
from app.materials.models import TechnicianProfile
from app.identity.models import User
from app.catalogs.models import City, Zone
from app.common.normalize import normalize_text
from app.settings import service as settings_service

_locks = {}
_locks_guard = threading.Lock()


def _lock_for(tech_id):
    with _locks_guard:
        if tech_id not in _locks:
            _locks[tech_id] = threading.Lock()
        return _locks[tech_id]


def _ensure_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def _parse_dt(value, default_tz="America/Bogota"):
    if not value:
        return None
    text = str(value)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        from zoneinfo import ZoneInfo
        dt = dt.replace(tzinfo=ZoneInfo(default_tz))
    return dt.astimezone(timezone.utc)


def _to_iso(dt):
    if not dt:
        return None
    dt = _ensure_aware(dt)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


BOGOTA = "America/Bogota"


def list_events(from_dt, to_dt, filters=None, for_user_id=None, for_user_roles=None):
    filters = filters or {}
    f = _parse_dt(from_dt)
    t = _parse_dt(to_dt)
    if not f or not t:
        return None, "invalid_range"
    if f >= t:
        return None, "invalid_range"
    if (t - f).days > 62:
        return None, "range_too_large"
    roles = for_user_roles or []
    q = WorkOrder.query.filter(WorkOrder.scheduled_at.isnot(None))
    q = q.filter(WorkOrder.scheduled_at >= f, WorkOrder.scheduled_at < t)
    if not filters.get("include_cancelled"):
        q = q.filter(WorkOrder.status != "cancelled")
    if for_user_id and "admin" not in roles and "dispatcher" not in roles:
        q = q.filter(WorkOrder.assigned_to_id == for_user_id)
    tid = filters.get("technician_id")
    if tid:
        q = q.filter(WorkOrder.assigned_to_id == int(tid))
    st = filters.get("status")
    if st:
        q = q.filter(WorkOrder.status == st)
    itype = filters.get("type")
    if itype:
        q = q.filter(db.or_(WorkOrder.installation_type_code == itype, WorkOrder.installation_type == itype))
    prio = filters.get("priority")
    if prio:
        q = q.filter(WorkOrder.priority == prio)
    city_id = filters.get("city_id")
    if city_id:
        q = q.filter(WorkOrder.city_id == int(city_id))
    zone_id = filters.get("zone_id")
    if zone_id:
        q = q.filter(WorkOrder.zone_id == int(zone_id))
    items = q.order_by(WorkOrder.scheduled_at).all()
    out = []
    for wo in items:
        start = wo.scheduled_at
        end = wo.scheduled_end or (start + timedelta(hours=1))
        techs = []
        if wo.assigned_to:
            techs.append({"id": wo.assigned_to.id, "name": wo.assigned_to.username})
        if wo.assigned_to_id and not wo.assigned_to:
            pass
        schedule_status = "scheduled" if wo.assigned_to_id else "unassigned"
        city_label = wo.city.label() if wo.city else None
        zone_label = wo.service_zone.name if wo.service_zone else (wo.zone or wo.legacy_zone)
        out.append({
            "order_id": wo.id,
            "order_code": f"OS-{wo.id:04d}",
            "title": wo.title,
            "start": _to_iso(start),
            "end": _to_iso(end),
            "status": wo.status,
            "priority": wo.priority,
            "technicians": techs,
            "schedule_status": schedule_status,
            "city": city_label,
            "zone": zone_label,
        })
    return out, None


def list_unassigned(page=1, page_size=20, for_user_id=None, for_user_roles=None):
    roles = for_user_roles or []
    q = WorkOrder.query.filter(db.or_(WorkOrder.scheduled_at.is_(None), WorkOrder.assigned_to_id.is_(None)))
    q = q.filter(WorkOrder.status.notin_(["cancelled", "completed"]))
    if for_user_id and "admin" not in roles and "dispatcher" not in roles:
        q = q.filter(WorkOrder.assigned_to_id == for_user_id)
    total = q.count()
    items = q.order_by(WorkOrder.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"items": [wo.to_dict() for wo in items], "total": total, "page": page, "page_size": page_size}, None


def technician_availability(tech_id, from_dt, to_dt):
    f = _parse_dt(from_dt)
    t = _parse_dt(to_dt)
    if not f or not t:
        return None, "invalid_range"
    orders = WorkOrder.query.filter(
        WorkOrder.assigned_to_id == int(tech_id),
        WorkOrder.scheduled_at.isnot(None),
        WorkOrder.scheduled_at >= f,
        WorkOrder.scheduled_at < t,
        WorkOrder.status.notin_(["cancelled"]),
    ).all()
    occupied = []
    for wo in orders:
        start = wo.scheduled_at
        end = wo.scheduled_end or (start + timedelta(hours=1))
        occupied.append({
            "start": _to_iso(start),
            "end": _to_iso(end),
            "order_id": wo.id,
            "order_code": f"OS-{wo.id:04d}",
        })
    return {"technician_id": int(tech_id), "occupied": occupied}, None


def _state_allows_schedule(wo, is_reprogram=False, roles=None):
    roles = roles or []
    if wo.status in ("completed", "cancelled"):
        return False
    if is_reprogram and wo.status == "in_progress":
        return "dispatcher" in roles
    return wo.status in ("pending", "assigned", "in_progress")


def schedule_order(order_id, data, user, roles):
    from app.identity.models import User as U
    wo = WorkOrder.query.filter_by(id=order_id).with_for_update().first()
    if not wo:
        return None, "not_found"
    if "dispatcher" not in roles:
        return None, "forbidden"
    # version check
    if "version" in data and data.get("version") is not None:
        if int(data["version"]) != int(wo.version or 0):
            return None, "stale_version"
    is_reprogram = wo.scheduled_at is not None
    # validate first
    vresult, verr = validate_schedule(order_id, data, roles)
    if verr:
        return None, verr
    if not vresult["ok"]:
        return None, _conflict_to_error(vresult["conflicts"][0]["code"])
    start = _parse_dt(data.get("start") or data.get("scheduled_at"))
    end = _parse_dt(data.get("end") or data.get("scheduled_end"))
    tech_ids = data.get("technician_ids")
    if tech_ids is None and data.get("technician_id") is not None:
        tech_ids = [data.get("technician_id")]
    if tech_ids is None and data.get("assigned_to_id") is not None:
        tech_ids = [data.get("assigned_to_id")]
    if tech_ids:
        tech_ids = [int(x) for x in tech_ids]
    techs = []
    for tid in (tech_ids or []):
        u = db.session.get(User, tid)
        if u:
            techs.append(u)
    primary_id = techs[0].id if techs else None
    locks = [_lock_for(tid) for tid in (tech_ids or [])]
    for lk in locks:
        lk.acquire()
    try:
        db.session.refresh(wo)
        if "version" in data and data.get("version") is not None:
            if int(data["version"]) != int(wo.version or 0):
                return None, "stale_version"
        # re-validate inside lock
        vresult2, verr2 = validate_schedule(order_id, data, roles)
        if verr2:
            return None, verr2
        if not vresult2["ok"]:
            return None, _conflict_to_error(vresult2["conflicts"][0]["code"])
        wo.scheduled_at = start
        wo.scheduled_end = end
        if "notes" in data or "schedule_notes" in data:
            wo.schedule_notes = data.get("notes") or data.get("schedule_notes")
        if tech_ids:
            wo.assigned_to_id = primary_id
            if wo.status == "pending":
                wo.status = "assigned"
        wo.version = (wo.version or 0) + 1
        from app.workorders.models import WorkOrderStatusHistory
        db.session.add(WorkOrderStatusHistory(
            work_order_id=wo.id,
            from_status=wo.status,
            to_status=wo.status,
            changed_by_id=user.id,
            notes=f"Programación: {start.isoformat()} - {end.isoformat()}" + (f" motivo={data.get('reason')}" if data.get("reason") else ""),
        ))
        db.session.commit()
        return wo, None
    finally:
        for lk in locks:
            lk.release()


def _conflict_to_error(code):
    return {
        "invalid_transition": "invalid_transition",
        "invalid_time": "invalid_time",
        "out_of_hours": "invalid_time",
        "duration_too_long": "duration_too_long",
        "invalid_technician": "invalid_technician",
        "technician_unavailable": "invalid_technician",
        "schedule_conflict": "schedule_conflict",
        "reason_required": "reason_required",
        "sunday_authorization_required": "sunday_authorization_required",
    }.get(code, "invalid_time")


def validate_schedule(order_id, data, roles):
    roles = roles or []
    if "dispatcher" not in roles:
        return None, "forbidden"
    wo = db.session.get(WorkOrder, order_id)
    if not wo:
        return None, "not_found"
    conflicts = []
    warnings = []
    is_reprogram = wo.scheduled_at is not None
    if not _state_allows_schedule(wo, is_reprogram, roles):
        conflicts.append({"code": "invalid_transition", "message": "la orden no admite programación en su estado actual"})
    start = _parse_dt(data.get("start") or data.get("scheduled_at"))
    end = _parse_dt(data.get("end") or data.get("scheduled_end"))
    if not start or not end:
        conflicts.append({"code": "invalid_time", "message": "fecha/hora inválida"})
    elif end <= start:
        conflicts.append({"code": "invalid_time", "message": "el fin debe ser posterior al inicio"})
    else:
        org = settings_service.get_organization()
        opset = settings_service.get_operations()
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(org.timezone or "America/Bogota")
        except Exception:
            tz = ZoneInfo("America/Bogota")
        local_start = start.astimezone(tz)
        local_end = end.astimezone(tz)
        work_days = [int(x) for x in str(opset.work_days).split(",") if x.strip()]
        if local_start.isoweekday() not in work_days:
            conflicts.append({"code": "invalid_time", "message": "día no laboral"})
        if local_start.strftime("%H:%M") < opset.work_start or local_end.strftime("%H:%M") > opset.work_end:
            conflicts.append({"code": "out_of_hours", "message": "fuera del horario operativo"})
        max_hours = int(data.get("max_hours", 8))
        if (end - start).total_seconds() > max_hours * 3600:
            conflicts.append({"code": "duration_too_long", "message": "duración demasiado larga"})
        # autorización de domingos y festivos (solo admin con motivo)
        try:
            import holidays as _holidays
            co_holidays = _holidays.Colombia()
        except Exception:
            co_holidays = set()
        is_restricted_day = (local_start.weekday() == 6) or (local_start.date() in co_holidays)
        if is_restricted_day:
            if "admin" not in roles:
                conflicts.append({"code": "sunday_authorization_required", "message": "programación en domingo o festivo requiere autorización del administrador"})
            elif not data.get("authorize_sunday"):
                conflicts.append({"code": "sunday_authorization_required", "message": "programación en domingo o festivo requiere authorize_sunday=true"})
            elif not data.get("reason"):
                conflicts.append({"code": "reason_required", "message": "motivo obligatorio para autorización"})
        # reason required when reprogramming
        if is_reprogram and not data.get("reason"):
            conflicts.append({"code": "reason_required", "message": "motivo del cambio obligatorio"})
        tech_ids = data.get("technician_ids")
        if tech_ids is None and data.get("technician_id") is not None:
            tech_ids = [data.get("technician_id")]
        if tech_ids is None and data.get("assigned_to_id") is not None:
            tech_ids = [data.get("assigned_to_id")]
        if tech_ids:
            tech_ids = [int(x) for x in tech_ids]
        margin = timedelta(minutes=opset.travel_margin_minutes or 0)
        for tid in (tech_ids or []):
            u = db.session.get(User, tid)
            if not u or not u.is_active or "technician" not in [r.name for r in (u.roles or [])]:
                conflicts.append({"code": "invalid_technician", "message": "técnico inválido", "technician_id": tid})
                continue
            prof = TechnicianProfile.query.filter_by(user_id=tid).first()
            if prof and (not prof.is_active or not prof.is_available):
                conflicts.append({"code": "technician_unavailable", "message": "técnico fuera de servicio", "technician_id": tid})
            # coverage check (warning if not covered)
            if prof and (wo.city_id or wo.zone_id):
                covered = False
                for c in (prof.coverages or []):
                    if c.city_id == wo.city_id and (wo.zone_id is None or c.zone_id == wo.zone_id or c.zone_id is None):
                        covered = True
                        break
                if not covered:
                    warnings.append({"code": "zone_not_covered", "message": "no cubre la zona", "technician_id": tid})
            # overlap check
            others = WorkOrder.query.filter(
                WorkOrder.assigned_to_id == tid,
                WorkOrder.id != wo.id,
                WorkOrder.scheduled_at.isnot(None),
                WorkOrder.status.notin_(["cancelled"]),
            ).all()
            for o in others:
                o_start = _ensure_aware(o.scheduled_at)
                o_end = _ensure_aware(o.scheduled_end) or (o_start + timedelta(hours=1))
                if (o_start - margin) < end and start < (o_end + margin):
                    conflicts.append({
                        "code": "schedule_conflict",
                        "message": "solape con otra visita",
                        "technician_id": tid,
                        "conflicting_order_id": o.id,
                        "conflicting_order_code": f"OS-{o.id:04d}",
                        "interval": [o_start.isoformat(), o_end.isoformat()],
                    })
    result = {"ok": len(conflicts) == 0, "conflicts": conflicts, "warnings": warnings}
    return result, None


def assign_order(order_id, data, user, roles):
    if "dispatcher" not in roles:
        return None, "forbidden"
    wo = WorkOrder.query.filter_by(id=order_id).with_for_update().first()
    if not wo:
        return None, "not_found"
    if wo.status in ("completed", "cancelled"):
        return None, "invalid_transition"
    tech_ids = data.get("technician_ids")
    if tech_ids is None and data.get("technician_id") is not None:
        tech_ids = [data.get("technician_id")]
    if tech_ids is None and data.get("assigned_to_id") is not None:
        tech_ids = [data.get("assigned_to_id")]
    if not tech_ids:
        # unassign
        wo.assigned_to_id = None
        wo.assigned_by_id = None
        if wo.status == "assigned":
            wo.status = "pending"
        wo.version = (wo.version or 0) + 1
        db.session.commit()
        return wo, None
    tech_ids = [int(x) for x in tech_ids]
    primary = None
    for tid in tech_ids:
        u = db.session.get(User, tid)
        if not u or not u.is_active or "technician" not in [r.name for r in (u.roles or [])]:
            return None, "invalid_technician"
        prof = TechnicianProfile.query.filter_by(user_id=tid).first()
        if prof and not prof.is_active:
            return None, "invalid_technician"
        primary = u
    # conflict check if scheduled
    if wo.scheduled_at:
        start = wo.scheduled_at
        end = wo.scheduled_end or (start + timedelta(hours=1))
        locks = [_lock_for(tid) for tid in tech_ids]
        for lk in locks:
            lk.acquire()
        try:
            for tid in tech_ids:
                others = WorkOrder.query.filter(
                    WorkOrder.assigned_to_id == tid,
                    WorkOrder.id != wo.id,
                    WorkOrder.scheduled_at.isnot(None),
                    WorkOrder.status.notin_(["cancelled"]),
                ).all()
                for o in others:
                    o_start = o.scheduled_at
                    o_end = o.scheduled_end or (o_start + timedelta(hours=1))
                    margin = timedelta(minutes=settings_service.get_operations().travel_margin_minutes or 0)
                    if (o_start - margin) < end and start < (o_end + margin):
                        return None, "schedule_conflict"
            wo.assigned_to_id = primary.id
            wo.assigned_by_id = user.id
            if wo.status == "pending":
                wo.status = "assigned"
            wo.version = (wo.version or 0) + 1
            db.session.commit()
            return wo, None
        finally:
            for lk in locks:
                lk.release()
    else:
        wo.assigned_to_id = primary.id
        if wo.status == "pending":
            wo.status = "assigned"
        wo.version = (wo.version or 0) + 1
        db.session.commit()
        return wo, None

