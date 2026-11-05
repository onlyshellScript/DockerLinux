import json
import threading
import time
from datetime import datetime, timezone

from app.extensions import db
from app.settings.models import (
    OrganizationSettings, OperationalSettings, SecuritySettings,
    NotificationSettings, UserNotificationPreference, AuditLog,
)

_cache = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 5


def _get_or_create(model):
    row = model.query.first()
    if not row:
        row = model()
        db.session.add(row)
        db.session.commit()
    return row


def invalidate():
    with _cache_lock:
        _cache.clear()


def _cached(key, loader):
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (now - entry[0]) < _CACHE_TTL:
            return entry[1]
    val = loader()
    with _cache_lock:
        _cache[key] = (now, val)
    return val


def get_organization():
    return _get_or_create(OrganizationSettings)


def get_operations():
    return _get_or_create(OperationalSettings)


def get_security():
    return _get_or_create(SecuritySettings)


def get_notifications():
    return _get_or_create(NotificationSettings)


def get_user_notifications(user_id):
    row = UserNotificationPreference.query.filter_by(user_id=user_id).first()
    if not row:
        row = UserNotificationPreference(user_id=user_id)
        db.session.add(row)
        db.session.commit()
    return row


def public_settings():
    def loader():
        org = get_organization()
        op = get_operations()
        return {
            "timezone": org.timezone,
            "work_start": op.work_start,
            "work_end": op.work_end,
            "default_visit_duration": op.default_visit_duration,
            "calendar_interval": op.calendar_interval,
            "company_name": org.company_name,
        }
    return _cached("public", loader)


def get_timezone():
    return get_organization().timezone or "America/Bogota"


def get_work_hours():
    op = get_operations()
    return op.work_start, op.work_end


def operational_dict():
    op = get_operations()
    return {
        "work_days": [int(x) for x in op.work_days.split(",") if x.strip()],
        "work_start": op.work_start,
        "work_end": op.work_end,
        "default_visit_duration": op.default_visit_duration,
        "max_visit_duration": op.max_visit_duration,
        "min_advance_hours": op.min_advance_hours,
        "travel_margin_minutes": op.travel_margin_minutes,
        "calendar_interval": op.calendar_interval,
        "stock_critical_threshold": op.stock_critical_threshold,
        "version": op.version,
    }


def _apply_patch(row, data, allowed_fields):
    for k, v in data.items():
        if k not in allowed_fields:
            return "unknown_field"
    # version check
    if "version" in data:
        if int(data["version"]) != int(row.version or 0):
            return "stale_version"
    for k, v in data.items():
        if k == "version":
            continue
        setattr(row, k, v)
    row.version = (row.version or 0) + 1
    return None


ORG_FIELDS = ["company_name", "nit", "admin_email", "contact_phone", "address", "city_id", "timezone"]
OP_FIELDS = ["work_days", "work_start", "work_end", "default_visit_duration", "max_visit_duration",
             "min_advance_hours", "travel_margin_minutes", "calendar_interval"]
SEC_FIELDS = ["session_inactivity_minutes", "session_max_hours", "password_min_length",
              "password_history_count", "lock_attempts", "lock_minutes", "temp_password_validity_days"]
NOTIF_FIELDS = ["preferences"]


def patch_organization(data, user_id):
    row = get_organization()
    # handle work_days list -> string
    if "work_days" in data and isinstance(data["work_days"], list):
        data = dict(data)
        data["work_days"] = ",".join(str(x) for x in data["work_days"])
    # timezone validation
    if "timezone" in data:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(data["timezone"])
        except Exception:
            return None, "invalid_timezone"
    if "city_id" in data and data["city_id"] is not None:
        from app.catalogs.models import City
        if not City.query.get(data["city_id"]):
            return None, "invalid_city"
    if "admin_email" in data:
        from app.common.normalize import normalize_text
        data = dict(data)
        data["admin_email"] = normalize_text(data["admin_email"])
    err = _apply_patch(row, data, ORG_FIELDS + ["version"])
    if err:
        return None, err
    row.updated_by_id = user_id
    # audit handled by caller? We'll audit here
    db.session.commit()
    invalidate()
    return row, None


def patch_operations(data, user_id):
    row = get_operations()
    if "work_days" in data and isinstance(data["work_days"], list):
        data = dict(data)
        data["work_days"] = ",".join(str(x) for x in data["work_days"])
    # validation
    if "work_start" in data or "work_end" in data:
        ws = data.get("work_start", row.work_start)
        we = data.get("work_end", row.work_end)
        if not (ws < we):
            return None, "invalid_range"
    if "default_visit_duration" in data:
        v = int(data["default_visit_duration"])
        if v < 15 or v > 480 or v % 5 != 0:
            return None, "invalid_value"
    if "max_visit_duration" in data:
        v = int(data["max_visit_duration"])
        if v < 15 or v > 480:
            return None, "invalid_value"
    if "min_advance_hours" in data:
        v = int(data["min_advance_hours"])
        if v < 0 or v > 720:
            return None, "invalid_value"
    if "travel_margin_minutes" in data:
        v = int(data["travel_margin_minutes"])
        if v < 0 or v > 120:
            return None, "invalid_value"
    if "calendar_interval" in data:
        if int(data["calendar_interval"]) not in (15, 30, 60):
            return None, "invalid_value"
    if "work_days" in data:
        days = [int(x) for x in str(data["work_days"]).split(",") if x.strip()]
        if len(days) < 1 or any(d < 1 or d > 7 for d in days):
            return None, "invalid_value"
    err = _apply_patch(row, data, OP_FIELDS + ["version"])
    if err:
        return None, err
    row.updated_by_id = user_id
    db.session.commit()
    invalidate()
    return row, None


def patch_security(data, user_id):
    row = get_security()
    err = _apply_patch(row, data, SEC_FIELDS + ["version"])
    if err:
        return None, err
    row.updated_by_id = user_id
    db.session.commit()
    invalidate()
    return row, None


def patch_notifications(data, user_id, user_scope=False):
    if user_scope:
        row = get_user_notifications(user_id)
    else:
        row = get_notifications()
    if "preferences" in data:
        # validate JSON
        try:
            json.loads(data["preferences"]) if isinstance(data["preferences"], str) else data["preferences"]
        except Exception:
            return None, "invalid_value"
        if not isinstance(data["preferences"], str):
            data = dict(data)
            data["preferences"] = json.dumps(data["preferences"])
    err = _apply_patch(row, data, NOTIF_FIELDS + ["version"])
    if err:
        return None, err
    if not user_scope:
        row.updated_by_id = user_id
    db.session.commit()
    invalidate()
    return row, None


def audit(user_id, username, section, field, old_value, new_value, result="applied", request_id=None):
    entry = AuditLog(
        user_id=user_id,
        username=username,
        section=section,
        field=field,
        old_value=None if old_value is None else str(old_value),
        new_value=None if new_value is None else str(new_value),
        result=result,
        request_id=request_id,
    )
    db.session.add(entry)
    return entry


def operations_impact(proposed):
    # dry-run: count scheduled orders violating new rules
    from app.workorders.models import WorkOrder
    op_cur = get_operations()
    org = get_organization()
    tz_name = proposed.get("timezone", org.timezone)
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/Bogota")
    work_start = proposed.get("work_start", op_cur.work_start)
    work_end = proposed.get("work_end", op_cur.work_end)
    work_days = proposed.get("work_days", op_cur.work_days)
    if isinstance(work_days, list):
        work_days = [int(x) for x in work_days]
    else:
        work_days = [int(x) for x in str(work_days).split(",") if x.strip()]
    max_dur = int(proposed.get("max_visit_duration", op_cur.max_visit_duration))
    margin = int(proposed.get("travel_margin_minutes", op_cur.travel_margin_minutes))
    items = []
    for wo in WorkOrder.query.filter(WorkOrder.scheduled_at.isnot(None), WorkOrder.status.notin_(["cancelled"])).all():
        start = wo.scheduled_at
        # convert to tz
        local = start.astimezone(tz)
        wd = local.isoweekday()  # 1..7
        violations = []
        if wd not in work_days:
            violations.append("día no laboral")
        if local.strftime("%H:%M") < work_start:
            violations.append("fuera de horario")
        end_local_time = (start + (wo.scheduled_end - wo.scheduled_at if wo.scheduled_end else __import__("datetime").timedelta(minutes=op_cur.default_visit_duration))).astimezone(tz)
        if end_local_time.strftime("%H:%M") > work_end:
            violations.append("fuera de horario")
        dur = int(((wo.scheduled_end or (wo.scheduled_at + __import__("datetime").timedelta(minutes=op_cur.default_visit_duration))) - wo.scheduled_at).total_seconds() / 60)
        if dur > max_dur:
            violations.append("duración máxima")
        if violations:
            items.append({
                "order_id": wo.id,
                "order_code": f"OS-{wo.id:04d}",
                "customer_name": wo.customer_name,
                "technician": wo.assigned_to.username if wo.assigned_to else None,
                "start": start.isoformat(),
                "violations": violations,
            })
    return {"count": len(items), "items": items}
