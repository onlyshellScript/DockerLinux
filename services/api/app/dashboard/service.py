from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.workorders.models import WorkOrder
from app.materials.models import Material, TechnicianProfile
from app.notifications.models import Notification

VALID_RANGES = (7, 14, 30)
ACTIVE_STATUSES = ("pending", "assigned", "in_progress")
DONE_STATUSES = ("completed",)
STACK_STATUSES = ("pending", "assigned", "in_progress", "completed", "cancelled")
ALL_STATUSES = ("pending", "assigned", "in_progress", "completed", "cancelled")
SLA_DAYS = 7          # plazo SLA (antes estaba fijo dentro del cálculo)
SPARK_POINTS = 10

# True si las columnas DateTime de la BD son "naive" (db.DateTime sin timezone=True).
# Solo afecta a las fechas que se envían a la consulta.
DB_NAIVE_UTC = True


# Convierte el valor al formato interno; recibe value; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def _parse_range(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        return 7
    return days if days in VALID_RANGES else 7


# Gestiona utc; recibe dt; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def _utc(dt):
    """Normaliza cualquier datetime (naive o aware) a aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# convierte un datetime aware UTC al formato naive/aware que espera la base de datos segun DB_NAIVE_UTC; entrada dt; salida datetime; sin efectos secundarios adicionales.
def _db(dt):
    """Convierte un datetime aware UTC al formato que espera la BD."""
    return dt.replace(tzinfo=None) if DB_NAIVE_UTC else dt


# _plural: devuelve la forma singular si n es 1 y la plural en caso contrario, para mensajes de conteo; entradas n, singular, plural; salida str; sin efectos secundarios.
def _plural(n, singular, plural):
    return singular if n == 1 else plural


# devuelve el porcentaje de variacion entre cur y prev redondeado a un decimal; devuelve None si prev es cero o falsy; entradas cur, prev; salida float o None; sin efectos secundarios.
def _delta_pct(cur, prev):
    if not prev:
        return None
    return round((cur - prev) / prev * 100, 1)


# _bucket: ubica un datetime en uno de los SPARK_POINTS intervalos entre start y el rango derivado de span_seconds; entradas dt, start, span_seconds; salida int indice; sin efectos secundarios.
def _bucket(dt, start, span_seconds):
    frac = (dt - start).total_seconds() / span_seconds
    return min(max(int(frac * SPARK_POINTS), 0), SPARK_POINTS - 1)


# Gestiona zone key; recibe wo; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def _zone_key(wo):
    if wo.zone_id and wo.service_zone:
        return wo.service_zone.name
    if wo.city_id and wo.city:
        return wo.city.label()
    return wo.zone or wo.legacy_zone or "Sin zona"


# Gestiona build tecnico summary; recibe user_id; interactua con la base de datos; devuelve el valor correspondiente.
def build_tecnico_summary(user_id):
    from app.workorders.models import WorkOrder, ALL_STATUSES
    from app.materials.models import TechnicianProfile
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    wos = WorkOrder.query.filter_by(assigned_to_id=user_id).all()
    counts = {s: 0 for s in ALL_STATUSES}
    for w in wos:
        if w.status in counts:
            counts[w.status] += 1
    hoy = 0
    en_proceso = 0
    completadas_hoy = 0
    pendientes_vencidas = 0
    for w in wos:
        sched = w.scheduled_at
        if sched is not None and sched.tzinfo is None:
            sched = sched.replace(tzinfo=timezone.utc)
        if sched is not None and today_start <= sched < today_end:
            hoy += 1
        if w.status == "in_progress":
            en_proceso += 1
        if w.status == "completed":
            done = w.completed_at or w.updated_at
            if done is not None and done.tzinfo is None:
                done = done.replace(tzinfo=timezone.utc)
            if done is not None and today_start <= done < today_end:
                completadas_hoy += 1
        # Pendientes o vencidas: abiertas (pending/assigned) sin fecha, atrasadas o de dias anteriores
        if w.status in ("pending", "assigned"):
            if sched is None or sched < today_start:
                pendientes_vencidas += 1
    profile = TechnicianProfile.query.filter_by(user_id=user_id).first()
    return {
        "user_id": user_id,
        "counts": counts,
        "resumen": {
            "hoy": hoy,
            "en_proceso": en_proceso,
            "completadas_hoy": completadas_hoy,
            "pendientes_vencidas": pendientes_vencidas,
        },
        "total": len(wos),
        "orders": [w.to_dict() for w in wos],
        "profile": profile.to_dict() if profile else None,
    }


# Gestiona build summary; recibe range_days, zone, city_id, zone_id, technician_id, user_id; interactua con la base de datos; devuelve el valor correspondiente.
def build_summary(range_days=7, zone=None, city_id=None, zone_id=None,
                  technician_id=None, user_id=None):
    days = _parse_range(range_days)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    prev_start = start - timedelta(days=days)
    span = (now - start).total_seconds()

    q_now, q_start, q_prev = _db(now), _db(start), _db(prev_start)

    base = WorkOrder.query
    if zone:
        base = base.filter(WorkOrder.zone == zone)
    if city_id is not None:
        base = base.filter(WorkOrder.city_id == int(city_id))
    if zone_id is not None:
        base = base.filter(WorkOrder.zone_id == int(zone_id))
    if technician_id is not None:
        base = base.filter(WorkOrder.assigned_to_id == technician_id)

    # "completada" se mide SIEMPRE con la misma fecha: completed_at (o updated_at si falta)
    done_col = func.coalesce(WorkOrder.completed_at, WorkOrder.updated_at)

    # ---- 1) órdenes creadas en el periodo (una sola consulta)
    period_orders = (
        base.filter(WorkOrder.created_at >= q_start, WorkOrder.created_at <= q_now)
        .options(joinedload(WorkOrder.service_zone), joinedload(WorkOrder.city))
        .all()
    )

    # ---- 2) órdenes activas hoy (snapshot, una sola consulta)
    active_orders = (
        base.filter(WorkOrder.status.in_(ACTIVE_STATUSES))
        .options(joinedload(WorkOrder.assigned_to))
        .all()
    )

    # ---- 3) completadas en el periodo (solo las columnas necesarias)
    completed_rows = (
        base.filter(WorkOrder.status.in_(DONE_STATUSES), done_col >= q_start, done_col <= q_now)
        .with_entities(WorkOrder.created_at, done_col)
        .all()
    )
    prev_completed = (
        base.filter(WorkOrder.status.in_(DONE_STATUSES), done_col >= q_prev, done_col < q_start)
        .count()
    )

    # ---- KPIs de resolución (solo órdenes con fechas válidas)
    hours_all = []
    sla_ok_all = 0
    spark_hours = [[] for _ in range(SPARK_POINTS)]
    spark_sla = [[] for _ in range(SPARK_POINTS)]
    spark_completed = [0] * SPARK_POINTS
    completed_series_dates = Counter()

    for created, done in completed_rows:
        done = _utc(done)
        created = _utc(created)
        idx = _bucket(done, start, span)
        spark_completed[idx] += 1
        completed_series_dates[done.date().isoformat()] += 1
        if created is None:
            continue
        hours = max((done - created).total_seconds() / 3600.0, 0.0)
        ok = hours <= SLA_DAYS * 24
        hours_all.append(hours)
        sla_ok_all += ok
        spark_hours[idx].append(hours)
        spark_sla[idx].append(ok)

    completed_count = len(completed_rows)
    sla_pct = round(sla_ok_all / len(hours_all) * 100, 1) if hours_all else 0.0
    mean_hours = round(sum(hours_all) / len(hours_all), 1) if hours_all else 0.0
    spark_sla_pct = [round(sum(b) / len(b) * 100, 1) if b else 0.0 for b in spark_sla]
    spark_mean = [round(sum(b) / len(b), 1) if b else 0.0 for b in spark_hours]

    # ---- series por día + sparkline de creadas
    labels, stack_counts = [], {}
    cur = start.date()
    while cur <= now.date():
        iso = cur.isoformat()
        labels.append(iso)
        stack_counts[iso] = {s: 0 for s in STACK_STATUSES}
        cur += timedelta(days=1)

    spark_created = [0] * SPARK_POINTS
    status_counter, priority_counter = Counter(), Counter()
    zone_breakdown, type_breakdown = Counter(), Counter()

    for wo in period_orders:
        created = _utc(wo.created_at)
        if created is not None:
            spark_created[_bucket(created, start, span)] += 1
            day = created.date().isoformat()
            key = "completed" if wo.status in DONE_STATUSES else wo.status  # 'closed' cuenta como completada
            if day in stack_counts and key in stack_counts[day]:
                stack_counts[day][key] += 1
        status_counter[wo.status] += 1
        priority_counter[wo.priority] += 1
        zone_breakdown[_zone_key(wo)] += 1
        type_breakdown[wo.installation_type or "Sin tipo"] += 1

    stack = {s: [stack_counts[d][s] for d in labels] for s in STACK_STATUSES}
    created_series = [sum(stack_counts[d].values()) for d in labels]
    completed_series = [completed_series_dates.get(d, 0) for d in labels]

    # ---- breakdowns (ahora respetan el periodo, salvo "load" que es la carga actual)
    status_breakdown = {s: status_counter.get(s, 0) for s in ALL_STATUSES}
    priority_breakdown = {p: priority_counter.get(p, 0) for p in ("high", "medium", "low")}
    zone_breakdown = dict(zone_breakdown)
    type_breakdown = dict(type_breakdown)

    load_breakdown = Counter()
    high_open = unassigned = 0
    for wo in active_orders:
        load_breakdown[wo.assigned_to.username if wo.assigned_to else "Sin asignar"] += 1
        high_open += wo.priority == "high"
        unassigned += wo.assigned_to_id is None
    load_breakdown = dict(load_breakdown)
    active_count = len(active_orders)

    # ---- técnicos y materiales (no dependen de los filtros de órdenes)
    technicians = [p.to_dict() for p in TechnicianProfile.query.all()]
    tech_total = len(technicians)
    tech_disp = sum(1 for t in technicians if t.get("is_available"))

    critical, low = [], []
    for m in Material.query.all():
        stock, minimum = m.current_stock or 0, m.min_stock or 0
        if stock <= minimum * 0.5:
            critical.append(m.to_dict())
        elif stock <= minimum:
            low.append(m.to_dict())

    insights = []
    if zone_breakdown and set(zone_breakdown) != {"Sin zona"}:
        top_zone = max(zone_breakdown, key=zone_breakdown.get)
        total = sum(zone_breakdown.values()) or 1
        pct = round(zone_breakdown[top_zone] / total * 100)
        insights.append({"kind": "info", "text": f"Zona con mayor concentración: {top_zone} ({pct}% del total)."})
    if high_open:
        insights.append({"kind": "warn", "text": f"{high_open} {_plural(high_open, 'orden', 'órdenes')} de prioridad Alta {_plural(high_open, 'abierta', 'abiertas')}."})
    if unassigned:
        insights.append({"kind": "danger", "text": f"{unassigned} {_plural(unassigned, 'orden', 'órdenes')} sin técnico asignado."})
    assigned_load = {k: v for k, v in load_breakdown.items() if k != "Sin asignar"}
    if assigned_load:
        top_tech = max(assigned_load, key=assigned_load.get)
        n = assigned_load[top_tech]
        insights.append({"kind": "info", "text": f"Técnico con mayor carga: {top_tech} ({n} {_plural(n, 'orden abierta', 'órdenes abiertas')})."})
    if critical:
        n = len(critical)
        insights.append({"kind": "danger", "text": f"{n} {_plural(n, 'material', 'materiales')} en stock crítico."})
    if not insights:
        insights.append({"kind": "ok", "text": "Sin hallazgos relevantes."})

    # ---- recientes y notificaciones
    recent = [
        wo.to_dict()
        for wo in base.options(joinedload(WorkOrder.assigned_to), joinedload(WorkOrder.service_zone), joinedload(WorkOrder.city))
        .order_by(WorkOrder.created_at.desc()).limit(10).all()
    ]
    # Solo las notificaciones del usuario que consulta; sin user_id no se devuelve ninguna.
    notifications = []
    if user_id is not None:
        notifications = [
            n.to_dict()
            for n in Notification.query.filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc()).limit(10).all()
        ]

    stock_alerts = len(critical) + len(low)
    kpis = [
        {"key": "active", "label": "Órdenes activas", "value": active_count,
         "detail": "pendientes + programadas + en proceso",
         "delta_pct": None,  # no hay histórico de "activas": no se puede comparar con el periodo anterior
         "up_is_good": False, "spark": spark_created},
        {"key": "completed", "label": "Completadas", "value": completed_count,
         "detail": "en el periodo", "delta_pct": _delta_pct(completed_count, prev_completed),
         "up_is_good": True, "spark": spark_completed},
        {"key": "sla", "label": "Cumplimiento SLA", "value": sla_pct,
         "detail": f"% dentro de {SLA_DAYS} días", "delta_pct": None,
         "up_is_good": True, "spark": spark_sla_pct},
        {"key": "mean_time", "label": "Tiempo medio", "value": mean_hours,
         "detail": "horas de resolución", "delta_pct": None,
         "up_is_good": False, "spark": spark_mean},
        {"key": "techs", "label": "Técnicos disp.", "value": f"{tech_disp}/{tech_total}",
         "detail": f"{tech_total - tech_disp} en campo", "delta_pct": None,
         "up_is_good": True, "spark": [tech_disp] * SPARK_POINTS},   # sin histórico: línea plana
        {"key": "stock", "label": "Alertas stock", "value": stock_alerts,
         "detail": f"{len(critical)} crítico", "delta_pct": None,
         "up_is_good": False, "spark": [stock_alerts] * SPARK_POINTS},  # sin histórico: línea plana
    ]

    return {
        "generated_at": now.isoformat(),
        "kpis": kpis,
        "series": {"labels": labels, "stack": stack, "created": created_series, "completed": completed_series},
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