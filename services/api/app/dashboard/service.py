from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.workorders.models import WorkOrder
from app.materials.models import Material, TechnicianProfile
from app.identity.models import User
from app.notifications.models import Notification


def _parse_range(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = 7
    if days not in (7, 14, 30):
        days = 7
    return days


def _period_bounds(days, now=None):
    now = now or datetime.now(timezone.utc)
    end = now
    start = now - timedelta(days=days)
    prev_start = start - timedelta(days=days)
    return start, end, prev_start


def _count_status(q, status):
    return q.filter(WorkOrder.status == status).count()


def build_summary(range_days=7, zone=None, city_id=None, zone_id=None, technician_id=None):
    days = _parse_range(range_days)
    start, end, prev_start = _period_bounds(days)

    base = WorkOrder.query
    if zone:
        base = base.filter(WorkOrder.zone == zone)
    if city_id:
        base = base.filter(WorkOrder.city_id == int(city_id))
    if zone_id:
        base = base.filter(WorkOrder.zone_id == int(zone_id))
    if technician_id:
        base = base.filter(WorkOrder.assigned_to_id == technician_id)

    # current period (by created_at)
    cur_q = base.filter(WorkOrder.created_at >= start, WorkOrder.created_at <= end)
    prev_q = base.filter(WorkOrder.created_at >= prev_start, WorkOrder.created_at < start)

    active_statuses = ("pending", "assigned", "in_progress")
    active_count = base.filter(WorkOrder.status.in_(active_statuses)).count()
    completed_count = base.filter(WorkOrder.status.in_(("completed", "closed"))).filter(
        WorkOrder.completed_at >= start, WorkOrder.completed_at <= end
    ).count() if False else base.filter(WorkOrder.status.in_(("completed", "closed"))).filter(
        WorkOrder.created_at >= start, WorkOrder.created_at <= end
    ).count()

    # SLA: completed within 7 days of creation (assumption)
    completed_orders = base.filter(WorkOrder.status.in_(("completed", "closed"))).filter(
        WorkOrder.created_at >= start, WorkOrder.created_at <= end
    ).all()
    sla_ok = 0
    for wo in completed_orders:
        end_dt = wo.completed_at or wo.updated_at or wo.created_at
        if end_dt and wo.created_at and (end_dt - wo.created_at).total_seconds() <= 7 * 86400:
            sla_ok += 1
    sla_pct = round((sla_ok / len(completed_orders) * 100), 1) if completed_orders else 0.0

    # mean resolution hours
    deltas = []
    for wo in completed_orders:
        end_dt = wo.completed_at or wo.updated_at or wo.created_at
        if end_dt and wo.created_at:
            deltas.append((end_dt - wo.created_at).total_seconds() / 3600.0)
    mean_hours = round(sum(deltas) / len(deltas), 1) if deltas else 0.0

    # previous period counts for delta
    prev_active = prev_q.filter(WorkOrder.status.in_(active_statuses)).count()
    prev_completed = prev_q.filter(WorkOrder.status.in_(("completed", "closed"))).count()

    def delta_pct(cur, prev):
        if prev == 0:
            return None
        return round((cur - prev) / prev * 100, 1)

    # sparklines: 10 points daily counts of created orders
    spark_labels = []
    spark_created = []
    for i in range(10):
        day_start = start + (end - start) * i / 10
        day_end = start + (end - start) * (i + 1) / 10
        c = base.filter(WorkOrder.created_at >= day_start, WorkOrder.created_at < day_end).count()
        spark_created.append(c)
    # completed spark
    spark_completed = []
    for i in range(10):
        day_start = start + (end - start) * i / 10
        day_end = start + (end - start) * (i + 1) / 10
        c = base.filter(WorkOrder.status.in_(("completed", "closed"))).filter(
            WorkOrder.created_at >= day_start, WorkOrder.created_at < day_end
        ).count()
        spark_completed.append(c)

    technicians = [p.to_dict() for p in TechnicianProfile.query.all()]
    tech_disp = sum(1 for t in technicians if t.get("is_available"))
    tech_total = len(technicians)

    materials = Material.query.all()
    critical = [m.to_dict() for m in materials if (m.current_stock or 0) <= (m.min_stock or 0) * 0.5]
    low = [m.to_dict() for m in materials if (m.min_stock or 0) * 0.5 < (m.current_stock or 0) <= (m.min_stock or 0)]

    # series by day
    labels = []
    day_counts = {}
    cur = start.date()
    end_date = end.date()
    while cur <= end_date:
        labels.append(cur.isoformat())
        day_counts[cur.isoformat()] = {s: 0 for s in ("pending", "assigned", "in_progress", "completed", "cancelled")}
        cur = cur + timedelta(days=1)
    for wo in base.filter(WorkOrder.created_at >= start, WorkOrder.created_at <= end).all():
        d = wo.created_at.date().isoformat() if wo.created_at else None
        if d in day_counts and wo.status in day_counts[d]:
            day_counts[d][wo.status] += 1
    stack = {s: [day_counts[d][s] for d in labels] for s in ("pending", "assigned", "in_progress", "completed", "cancelled")}
    created_series = [sum(day_counts[d].values()) for d in labels]
    completed_series = [0] * len(labels)
    # completed by updated_at
    for wo in base.filter(WorkOrder.status.in_(("completed", "closed"))).filter(WorkOrder.updated_at >= start, WorkOrder.updated_at <= end).all():
        d = wo.updated_at.date().isoformat() if wo.updated_at else None
        if d in labels:
            idx = labels.index(d)
            completed_series[idx] += 1

    # breakdowns
    status_breakdown = {}
    for s in ("pending", "assigned", "in_progress", "completed", "closed", "cancelled"):
        status_breakdown[s] = base.filter(WorkOrder.status == s).count()
    zone_breakdown = {}
    for wo in base.all():
        if wo.zone_id and wo.service_zone:
            key = wo.service_zone.name
        elif wo.city_id and wo.city:
            key = wo.city.label()
        else:
            key = wo.zone or wo.legacy_zone or "Sin zona"
        zone_breakdown[key] = zone_breakdown.get(key, 0) + 1
    type_breakdown = {}
    for wo in base.all():
        key = wo.installation_type or "Sin tipo"
        type_breakdown[key] = type_breakdown.get(key, 0) + 1
    priority_breakdown = {}
    for p in ("high", "medium", "low"):
        priority_breakdown[p] = base.filter(WorkOrder.priority == p).count()
    load_breakdown = {}
    for wo in base.filter(WorkOrder.status.in_(active_statuses)).all():
        key = wo.assigned_to.username if wo.assigned_to else "Sin asignar"
        load_breakdown[key] = load_breakdown.get(key, 0) + 1

    # insights
    insights = []
    # zone concentration (omit if only "Sin zona")
    if zone_breakdown and not (len(zone_breakdown) == 1 and "Sin zona" in zone_breakdown):
        top_zone = max(zone_breakdown, key=lambda k: zone_breakdown[k])
        total = sum(zone_breakdown.values()) or 1
        pct = round(zone_breakdown[top_zone] / total * 100)
        insights.append({"kind": "info", "text": f"Zona con mayor concentración: {top_zone} ({pct}% del total)."})
    high_open = base.filter(WorkOrder.priority == "high", WorkOrder.status.in_(active_statuses)).count()
    if high_open:
        n = high_open
        insights.append({"kind": "warn", "text": f"{n} orden{'es' if n != 1 else ''} de prioridad Alta abiertas."})
    unassigned = base.filter(WorkOrder.assigned_to_id.is_(None), WorkOrder.status.in_(active_statuses)).count()
    if unassigned:
        n = unassigned
        insights.append({"kind": "danger", "text": f"{n} orden{'es' if n != 1 else ''} sin técnico asignado."})
    # top tech excluding "Sin asignar"
    load_filtered = {k: v for k, v in load_breakdown.items() if k != "Sin asignar"}
    if load_filtered:
        top_tech = max(load_filtered, key=lambda k: load_filtered[k])
        n = load_filtered[top_tech]
        insights.append({"kind": "info", "text": f"Técnico con mayor carga: {top_tech} ({n} orden{'es' if n != 1 else ''} abiertas)."})
    if critical:
        n = len(critical)
        insights.append({"kind": "danger", "text": f"{n} material{'es' if n != 1 else ''} en stock crítico."})
    if not insights:
        insights.append({"kind": "ok", "text": "Sin hallazgos relevantes."})

    # recent orders
    recent = [wo.to_dict() for wo in base.order_by(WorkOrder.created_at.desc()).limit(10).all()]
    notifications = [n.to_dict() for n in Notification.query.order_by(Notification.created_at.desc()).limit(10).all()] if hasattr(Notification, "to_dict") else []

    kpis = [
        {"key": "active", "label": "Órdenes activas", "value": active_count, "detail": "pendientes + programadas + en proceso", "delta_pct": delta_pct(active_count, prev_active), "up_is_good": False, "spark": spark_created},
        {"key": "completed", "label": "Completadas", "value": completed_count, "detail": "en el periodo", "delta_pct": delta_pct(completed_count, prev_completed), "up_is_good": True, "spark": spark_completed},
        {"key": "sla", "label": "Cumplimiento SLA", "value": sla_pct, "detail": "% dentro de plazo", "delta_pct": None, "up_is_good": True, "spark": spark_completed},
        {"key": "mean_time", "label": "Tiempo medio", "value": mean_hours, "detail": "horas de resolución", "delta_pct": None, "up_is_good": False, "spark": spark_completed},
        {"key": "techs", "label": "Técnicos disp.", "value": f"{tech_disp}/{tech_total}", "detail": f"{tech_total - tech_disp} en campo", "delta_pct": None, "up_is_good": True, "spark": [tech_disp] * 10},
        {"key": "stock", "label": "Alertas stock", "value": len(critical) + len(low), "detail": f"{len(critical)} crítico", "delta_pct": None, "up_is_good": False, "spark": [len(critical) + len(low)] * 10},
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kpis": kpis,
        "series": {
            "labels": labels,
            "stack": stack,
            "created": created_series,
            "completed": completed_series,
        },
        "breakdowns": {
            "status": status_breakdown,
            "zone": zone_breakdown,
            "type": type_breakdown,
            "priority": priority_breakdown,
            "load": load_breakdown,
        },
        "insights": insights,
        "recent_orders": recent,
        "technicians": technicians,
        "notifications": notifications,
        "stock": {"critical": critical, "low": low},
    }
