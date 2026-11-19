"""Obtencion y normalizacion de datos para exportaciones.

Cada fuente reutiliza los servicios del modulo (mismos filtros y reglas de acceso que la UI) y devuelve
filas con TIPOS REALES (int/float/Decimal/datetime/str), nunca texto preformateado. El formato visual
lo deciden los renderizadores segun el tipo de columna.
"""
from collections import Counter, defaultdict
from datetime import datetime, time, timezone
from decimal import Decimal

from app.extensions import db

ORDER_STATUS_LABEL = {"pending": "Pendiente", "assigned": "Programada", "in_progress": "En proceso", "completed": "Completada",
                      "closed": "Cerrada", "cancelled": "Cancelada"}
PRIORITY_LABEL = {"high": "Alta", "medium": "Media", "low": "Baja"}
STOCK_LABEL = {"ok": "Normal", "low": "Bajo", "critical": "Crítico"}
REQUEST_LABEL = {"DRAFT": "Borrador", "SUBMITTED": "Enviada", "APPROVED": "Aprobada", "PARTIALLY_APPROVED": "Aprobada parcialmente",
                 "REJECTED": "Rechazada", "PARTIALLY_DELIVERED": "Entregada parcialmente", "DELIVERED": "Entregada", "CANCELLED": "Cancelada"}
EVIDENCE_LABEL = {"DRAFT": "Borrador", "SUBMITTED": "Enviado", "UNDER_REVIEW": "En revisión", "CORRECTION_REQUIRED": "Requiere corrección",
                  "RESUBMITTED": "Reenviado", "APPROVED": "Aprobado", "REJECTED": "Rechazado"}
CATEGORY_LABEL = {"BEFORE": "Antes", "DURING": "Durante", "AFTER": "Después", "ADDITIONAL": "Adicional"}
ROLE_LABEL = {"admin": "Administrador", "dispatcher": "Coordinador", "technician": "Técnico"}


class ExportError(ValueError):
    """Error de validacion de parametros (se devuelve como 422)."""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.message, self.field = message, field


# ---------------------------------------------------------------- utilidades de fecha
def org_tz():
    from zoneinfo import ZoneInfo
    try:
        from app.settings.service import get_organization
        return ZoneInfo(get_organization().timezone or "America/Bogota")
    except Exception:  # pragma: no cover - zona por defecto si la configuracion no esta disponible
        return ZoneInfo("America/Bogota")


def to_local(dt):
    """datetime -> hora local de la organizacion, sin tzinfo (Excel no admite zona)."""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(org_tz()).replace(tzinfo=None)


def parse_period(params):
    """date_from/date_to (YYYY-MM-DD, dia completo en hora local) -> (inicio_utc, fin_utc)."""
    tz = org_tz()
    out = []
    for key, t in (("date_from", time.min), ("date_to", time.max)):
        raw = (params.get(key) or "").strip()
        if not raw:
            out.append(None)
            continue
        try:
            d = datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except ValueError:
            raise ExportError("Fecha inválida (use AAAA-MM-DD)", key)
        out.append(datetime.combine(d, t, tzinfo=tz).astimezone(timezone.utc))
    if out[0] and out[1] and out[0] > out[1]:
        raise ExportError("La fecha inicial no puede ser posterior a la final", "date_from")
    return out[0], out[1]


def _in_period(dt, start, end):
    if dt is None:
        return start is None and end is None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (start is None or dt >= start) and (end is None or dt <= end)


def _user_names(ids):
    from app.identity.models import User
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: u.username for u in User.query.filter(User.id.in_(ids)).all()}


# ---------------------------------------------------------------- MATERIALES
def src_materials(t, params, ctx):
    from app.materials.service import list_materials
    res = list_materials(q=params.get("q") or None, status=params.get("status") or None, is_active=True, page=1, page_size=100000)
    cat = params.get("category")
    status_in = t.fixed_filters.get("status_in")
    rows = []
    for item in res["items"]:
        m, st = item["material"], item["status"]
        if status_in and st not in status_in:
            continue
        category = getattr(m, "category", None) or ""
        if cat and category != cat:
            continue
        stock, mn = float(m.current_stock or 0), float(m.min_stock or 0)
        price = Decimal(m.unit_price or 0)
        rows.append({
            "code": m.code or "", "name": m.name or "", "category": category or "Sin categoría", "unit": m.unit or "",
            "stock": stock, "min_stock": mn, "level": (min(stock / mn, 9.99) if mn > 0 else (1.0 if stock > 0 else 0.0)),
            "status": STOCK_LABEL.get(st, st), "_status_key": st, "unit_price": price, "value": price * Decimal(str(stock)),
            "shortage": max(mn - stock, 0.0),
        })
    return rows


# ---------------------------------------------------------------- ÓRDENES
def src_orders(t, params, ctx):
    from app.reportes.service import build_report
    start, end = parse_period(params)
    date_field = params.get("date_field") if params.get("date_field") in ("created_at", "scheduled_at") else "created_at"
    rows, page = [], 1
    while True:
        try:
            data = build_report(estado=params.get("status") or None, tecnico_id=params.get("technician_id") or None,
                                zona=params.get("zone") or None,
                                desde=start.isoformat() if start else None, hasta=end.isoformat() if end else None,
                                pagina=page, por_pagina=100, campo_fecha=date_field,
                                for_user_id=ctx["user_id"], for_user_roles=ctx["roles"])
        except ValueError as exc:
            raise ExportError(str(exc))
        for o in data.get("items", []):
            rows.append({
                "code": f"OS-{o['id']:04d}", "_id": o["id"], "title": o.get("title") or "", "customer": o.get("customer_name") or "",
                "address": o.get("address") or "", "zone": o.get("zone") or o.get("legacy_zone") or "",
                "installation_type": o.get("installation_type") or "", "technician": (o.get("assigned_to") or {}).get("username") or "Sin asignar",
                "status": ORDER_STATUS_LABEL.get(o.get("status"), o.get("status")), "_status_key": o.get("status"),
                "priority": PRIORITY_LABEL.get(o.get("priority"), o.get("priority") or ""),
                "created_at": to_local(o.get("created_at")), "scheduled_at": to_local(o.get("scheduled_at")),
                "completed_at": to_local(o.get("completed_at")),
            })
        if page * 100 >= data.get("total", 0) or not data.get("items"):
            break
        page += 1
    return rows


# ---------------------------------------------------------------- TÉCNICOS
def _profiles(params=None):
    from app.technicians.service import list_technicians
    res = list_technicians(active=True, page=1, page_size=100000)
    items = res["items"]
    avail = (params or {}).get("availability")
    if avail == "available":
        items = [p for p in items if p.is_available]
    elif avail == "unavailable":
        items = [p for p in items if not p.is_available]
    return items


def _profile_name(p):
    full = " ".join(x for x in (p.first_name, p.last_name) if x).strip()
    return full or (p.user.username if p.user else f"Técnico {p.id}")


def src_technicians(t, params, ctx):
    rows = []
    for p in _profiles(params):
        d = p.to_dict()
        zones = d.get("zones") or []
        zone_txt = ", ".join(z.get("zone_name") or z.get("city_label") or "" for z in zones if isinstance(z, dict)) or (p.legacy_zone or "")
        rows.append({
            "name": _profile_name(p), "username": p.user.username if p.user else "", "document": p.document or p.document_number or "",
            "phone": p.phone or "", "email": p.email or (p.user.email if p.user else ""), "specialty": p.specialty or "",
            "zones": zone_txt, "available": "Sí" if p.is_available else "No", "active": "Sí" if p.is_active else "No",
        })
    return rows


def src_technician_assignments(t, params, ctx):
    from app.workorders.models import WorkOrder
    start, end = parse_period(params)
    rows = []
    for p in _profiles():
        orders = WorkOrder.query.filter(WorkOrder.assigned_to_id == p.user_id).all() if p.user_id else []
        c = Counter(o.status for o in orders if o.status in ("pending", "assigned", "in_progress"))
        done = sum(1 for o in orders if o.status in ("completed", "closed") and _in_period(o.completed_at or o.updated_at, start, end))
        rows.append({"name": _profile_name(p), "pending": c["pending"], "assigned": c["assigned"], "in_progress": c["in_progress"],
                     "open_total": sum(c.values()), "completed": done, "available": "Sí" if p.is_available else "No"})
    return rows


def src_technician_activity(t, params, ctx):
    from app.workorders.models import WorkOrderStatusHistory
    start, end = parse_period(params)
    profiles = {p.user_id: p for p in _profiles() if p.user_id}
    q = WorkOrderStatusHistory.query.filter(WorkOrderStatusHistory.changed_by_id.in_(list(profiles) or [-1]))
    if start:
        q = q.filter(WorkOrderStatusHistory.created_at >= start)
    if end:
        q = q.filter(WorkOrderStatusHistory.created_at <= end)
    agg = defaultdict(lambda: {"changes": 0, "started": 0, "completed": 0, "orders": set(), "last": None})
    for h in q.all():
        a = agg[h.changed_by_id]
        a["changes"] += 1
        a["started"] += h.to_status == "in_progress"
        a["completed"] += h.to_status == "completed"
        a["orders"].add(h.work_order_id)
        if h.created_at and (a["last"] is None or h.created_at > a["last"]):
            a["last"] = h.created_at
    rows = []
    for uid, p in profiles.items():
        a = agg.get(uid)
        rows.append({"name": _profile_name(p), "changes": a["changes"] if a else 0, "started": a["started"] if a else 0,
                     "completed": a["completed"] if a else 0, "orders": len(a["orders"]) if a else 0,
                     "last_activity": to_local(a["last"]) if a else None})
    return rows


# ---------------------------------------------------------------- SOLICITUDES
def src_requests(t, params, ctx):
    from app.materials.models import TechnicianProfile
    from app.materials.service import list_requests_filtered
    start, end = parse_period(params)
    items, _ = list_requests_filtered(status=params.get("status") or None, user_id=ctx["user_id"], roles=ctx["roles"], page=1, page_size=100000)
    status_in = t.fixed_filters.get("status_in")
    items = [r for r in items if (not status_in or r.status in status_in) and _in_period(r.created_at, start, end)]
    users = _user_names(r.requester_id for r in items)
    techs = {p.id: _profile_name(p) for p in TechnicianProfile.query.filter(TechnicianProfile.id.in_({r.technician_id for r in items if r.technician_id} or {-1})).all()}
    now = datetime.now(timezone.utc)
    rows = []
    for r in items:
        its = list(r.items or [])
        req = sum(float(i.quantity_requested if i.quantity_requested is not None else (i.quantity or 0)) for i in its)
        app_ = sum(float(i.quantity_approved or 0) for i in its)
        dlv = sum(float(i.quantity_delivered or 0) for i in its)
        created = r.created_at.replace(tzinfo=timezone.utc) if r.created_at and r.created_at.tzinfo is None else r.created_at
        rows.append({
            "code": f"SM-{r.id:04d}", "order": f"OS-{r.work_order_id:04d}" if r.work_order_id else "—",
            "requester": users.get(r.requester_id, ""), "technician": techs.get(r.technician_id, "—"),
            "status": REQUEST_LABEL.get(r.status, r.status), "_status_key": r.status, "items": len(its),
            "requested": req, "approved": app_, "delivered": dlv, "pending_qty": max((app_ or req) - dlv, 0.0),
            "fulfillment": (dlv / req) if req else 0.0, "reason": r.reason or "", "approval_reason": r.approval_reason or "",
            "created_at": to_local(r.created_at), "age_days": (now - created).days if created else None,
        })
    return rows


# ---------------------------------------------------------------- EVIDENCIAS
def src_evidence(t, params, ctx):
    from app.evidence.models import VisitEvidence
    from app.workorders.models import WorkOrder
    start, end = parse_period(params)
    q = VisitEvidence.query
    if params.get("status"):
        q = q.filter(VisitEvidence.status == params["status"])
    if params.get("category"):
        q = q.filter(VisitEvidence.category == params["category"])
    if start:
        q = q.filter(VisitEvidence.received_at >= start)
    if end:
        q = q.filter(VisitEvidence.received_at <= end)
    evs = q.all()
    orders = {w.id: w for w in WorkOrder.query.filter(WorkOrder.id.in_({e.work_order_id for e in evs} or {-1})).all()}
    users = _user_names(e.uploaded_by_id for e in evs)
    return [{
        "order": f"OS-{e.work_order_id:04d}", "customer": (orders.get(e.work_order_id).customer_name if orders.get(e.work_order_id) else "") or "",
        "category": CATEGORY_LABEL.get(e.category, e.category or ""), "file": e.original_name or "", "description": e.description or "",
        "size_kb": round((e.size_bytes or 0) / 1024, 1), "status": EVIDENCE_LABEL.get(e.status, e.status or ""),
        "uploaded_by": users.get(e.uploaded_by_id, ""), "received_at": to_local(e.received_at),
    } for e in evs]


def src_evidence_by_order(t, params, ctx):
    from app.evidence.models import VisitEvidence, VisitSignature
    from app.evidence.service import get_expediente_status
    from app.workorders.models import WorkOrder
    start, end = parse_period(params)
    evs = [e for e in VisitEvidence.query.all() if _in_period(e.received_at, start, end)]
    by_wo = defaultdict(list)
    for e in evs:
        by_wo[e.work_order_id].append(e)
    orders = {w.id: w for w in WorkOrder.query.filter(WorkOrder.id.in_(list(by_wo) or [-1])).all()}
    sigs = defaultdict(list)
    for s in VisitSignature.query.filter(VisitSignature.work_order_id.in_(list(by_wo) or [-1])).all():
        sigs[s.work_order_id].append(s)
    rows = []
    for wo_id, items in by_wo.items():
        st = (get_expediente_status(wo_id) or {}).get("status")
        if params.get("status") and st != params["status"]:
            continue
        w = orders.get(wo_id)
        c = Counter(e.category for e in items)
        sg = sigs.get(wo_id) or []
        rows.append({
            "order": f"OS-{wo_id:04d}", "customer": (w.customer_name if w else "") or "",
            "technician": (w.assigned_to.username if w and w.assigned_to else "Sin asignar"), "files": len(items),
            "before": c["BEFORE"], "during": c["DURING"], "after": c["AFTER"],
            "signature": ("Negativa" if all(s.refused for s in sg) else "Registrada") if sg else "Sin firma",
            "status": EVIDENCE_LABEL.get(st, st or ""), "last_received": to_local(max((e.received_at for e in items if e.received_at), default=None)),
        })
    return rows


# ---------------------------------------------------------------- REPORTES
def _summary_data(params):
    from app.dashboard.service import build_summary
    rng = params.get("range") or "7"
    if rng not in ("7", "14", "30"):
        raise ExportError("Período inválido", "range")
    return build_summary(range_days=int(rng))


KPI_LABEL = {"active": "Órdenes activas", "completed": "Órdenes completadas", "sla": "Cumplimiento SLA", "mean_time": "Tiempo medio de atención",
             "techs": "Técnicos disponibles", "stock": "Alertas de stock"}


def src_kpis(t, params, ctx):
    d = _summary_data(params)
    return [{"indicator": KPI_LABEL.get(k.get("key"), k.get("label") or k.get("key")), "value": str(k.get("value")),
             "delta": (k["delta_pct"] / 100.0) if k.get("delta_pct") is not None else None} for k in d.get("kpis", [])]


def src_operations(t, params, ctx):
    d = _summary_data(params)
    bd = d.get("breakdowns", {})
    rows = []
    for dim, key, labels in (("Estado", "status", ORDER_STATUS_LABEL), ("Prioridad", "priority", PRIORITY_LABEL), ("Zona", "zone", {}), ("Tipo de instalación", "type", {})):
        data = bd.get(key) or {}
        total = sum(int(v or 0) for v in data.values())
        for cat, v in sorted(data.items(), key=lambda kv: -int(kv[1] or 0)):
            rows.append({"dimension": dim, "category": labels.get(cat, cat), "count": int(v or 0), "share": (int(v or 0) / total) if total else 0.0})
    return rows


# ---------------------------------------------------------------- USUARIOS (solo admin; nunca hash ni tokens)
def src_users(t, params, ctx):
    from app.identity.service import list_users
    if params.get("status") not in (None, "", "active", "inactive"):
        raise ExportError("Estado inválido", "status")
    users = list_users(role=params.get("role") or None, status=params.get("status") or None)
    return [{
        "username": u.username, "email": u.email, "roles": ", ".join(ROLE_LABEL.get(r.name, r.name) for r in u.roles) or "Sin rol",
        "status": "Activa" if u.is_active else "Inactiva", "must_change": "Sí" if u.must_change_password else "No",
        "created_at": to_local(u.created_at), "last_login": to_local(u.last_login),
    } for u in users]


def src_users_roles(t, params, ctx):
    from app.identity.service import list_users
    users = list_users()
    agg = defaultdict(lambda: [0, 0])
    for u in users:
        for r in (u.roles or [None]):
            name = ROLE_LABEL.get(r.name, r.name) if r else "Sin rol"
            agg[name][0 if u.is_active else 1] += 1
    total = sum(a + i for a, i in agg.values())
    return [{"role": k, "active": a, "inactive": i, "total": a + i, "share": ((a + i) / total) if total else 0.0}
            for k, (a, i) in sorted(agg.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))]


SOURCES = {
    "materials": src_materials, "orders": src_orders, "technicians": src_technicians,
    "technician_assignments": src_technician_assignments, "technician_activity": src_technician_activity,
    "requests": src_requests, "evidence": src_evidence, "evidence_by_order": src_evidence_by_order,
    "kpis": src_kpis, "operations": src_operations, "users": src_users, "users_roles": src_users_roles,
}


# ---------------------------------------------------------------- RESÚMENES  -> [(etiqueta, valor, tipo)]
def _count_by(rows, key):
    return Counter(r.get(key) for r in rows)


def sum_materials(rows, params):
    c = _count_by(rows, "_status_key")
    return [("Materiales", len(rows), "int"), ("Stock normal", c["ok"], "int"), ("Stock bajo", c["low"], "int"), ("Stock crítico", c["critical"], "int")]


def sum_materials_valued(rows, params):
    total = sum((r["value"] for r in rows), Decimal(0))
    top = max(rows, key=lambda r: r["value"], default=None)
    return [("Materiales", len(rows), "int"), ("Valor total del inventario", total, "money"),
            ("Material de mayor valor", top["name"] if top else "—", "text")]


def sum_orders(rows, params):
    c = _count_by(rows, "_status_key")
    out = [("Órdenes", len(rows), "int")]
    for k in ("pending", "assigned", "in_progress", "completed", "cancelled"):
        if c[k]:
            out.append((ORDER_STATUS_LABEL[k], c[k], "int"))
    return out


def sum_orders_period(rows, params):
    days = Counter(r["created_at"].date() for r in rows if r.get("created_at"))
    busiest = max(days.items(), key=lambda kv: kv[1], default=None)
    out = sum_orders(rows, params)
    out.append(("Días con órdenes", len(days), "int"))
    if busiest:
        out.append(("Día con más órdenes", f"{busiest[0].strftime('%d/%m/%Y')} ({busiest[1]})", "text"))
    return out


def sum_technicians(rows, params):
    return [("Técnicos", len(rows), "int"), ("Disponibles", sum(r["available"] == "Sí" for r in rows), "int")]


def sum_tech_assign(rows, params):
    return [("Técnicos", len(rows), "int"), ("Órdenes abiertas asignadas", sum(r["open_total"] for r in rows), "int"),
            ("Completadas en el período", sum(r["completed"] for r in rows), "int")]


def sum_tech_activity(rows, params):
    return [("Técnicos", len(rows), "int"), ("Cambios de estado", sum(r["changes"] for r in rows), "int"),
            ("Técnicos sin actividad", sum(1 for r in rows if not r["changes"]), "int")]


def sum_requests(rows, params):
    return [("Solicitudes", len(rows), "int"), ("Cantidad solicitada", sum(r["requested"] for r in rows), "number"),
            ("Cantidad entregada", sum(r["delivered"] for r in rows), "number")]


def sum_evidence(rows, params):
    return [("Evidencias", len(rows), "int"), ("Órdenes con evidencias", len({r["order"] for r in rows}), "int"),
            ("Tamaño total (KB)", round(sum(r["size_kb"] for r in rows), 1), "number")]


def sum_evidence_by_order(rows, params):
    return [("Expedientes", len(rows), "int"), ("Evidencias", sum(r["files"] for r in rows), "int"),
            ("Sin firma", sum(r["signature"] == "Sin firma" for r in rows), "int")]


def sum_kpis(rows, params):
    return [("Período", f"Últimos {params.get('range') or '7'} días", "text"), ("Indicadores", len(rows), "int")]


def sum_operations(rows, params):
    st = [r for r in rows if r["dimension"] == "Estado"]
    return [("Período", f"Últimos {params.get('range') or '7'} días", "text"), ("Órdenes analizadas", sum(r["count"] for r in st), "int")]


def sum_users(rows, params):
    if rows and "total" in rows[0]:
        return [("Cuentas", sum(r["total"] for r in rows), "int"), ("Activas", sum(r["active"] for r in rows), "int"),
                ("Inactivas", sum(r["inactive"] for r in rows), "int")]
    return [("Cuentas", len(rows), "int"), ("Activas", sum(r["status"] == "Activa" for r in rows), "int"),
            ("Inactivas", sum(r["status"] == "Inactiva" for r in rows), "int")]


SUMMARIES = {
    "materials": sum_materials, "materials_valued": sum_materials_valued, "orders": sum_orders, "orders_period": sum_orders_period,
    "technicians": sum_technicians, "technician_assignments": sum_tech_assign, "technician_activity": sum_tech_activity,
    "requests": sum_requests, "evidence": sum_evidence, "evidence_by_order": sum_evidence_by_order, "kpis": sum_kpis,
    "operations": sum_operations, "users": sum_users,
}


def option_values(source):
    """Opciones dinamicas para filtros select."""
    if source == "technicians":
        return [{"value": str(p.user_id), "label": _profile_name(p)} for p in _profiles() if p.user_id]
    if source == "categories":
        from app.materials.models import MaterialCategory
        return [{"value": c.name, "label": c.name} for c in MaterialCategory.query.filter_by(is_active=True).order_by(MaterialCategory.name).all()]
    return []
