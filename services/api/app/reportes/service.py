# Módulo de la aplicación.
from datetime import datetime

from sqlalchemy.orm import selectinload

from app.extensions import db
from app.workorders.models import WorkOrder, ALL_STATUSES


# Convierte el valor al formato interno; recibe value; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def _parse_iso(value):
    if value is None or value == "":
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("fecha debe estar en formato ISO (YYYY-MM-DD o ISO 8601)")


# Gestiona build report; recibe estado, tecnico_id, zona, desde, hasta, pagina, por_pagina, campo_fecha, for_user_id, for_user_roles; interactua con la base de datos; devuelve el valor correspondiente.
def build_report(estado=None, tecnico_id=None, zona=None, desde=None,
                 hasta=None, pagina=1, por_pagina=10, campo_fecha="created_at",
                 for_user_id=None, for_user_roles=None):
    if estado is not None and estado != "" and estado not in ALL_STATUSES:
        raise ValueError("estado invalido")
    if campo_fecha not in ("created_at", "scheduled_at"):
        raise ValueError("campo_fecha debe ser created_at o scheduled_at")

    fecha_col = getattr(WorkOrder, campo_fecha)

    desde_dt = _parse_iso(desde)
    hasta_dt = _parse_iso(hasta)
    if desde_dt is not None and hasta_dt is not None and desde_dt > hasta_dt:
        raise ValueError("desde debe ser menor o igual a hasta")

    try:
        page = max(1, int(pagina or 1))
    except (TypeError, ValueError):
        raise ValueError("pagina debe ser entero")
    try:
        per_page = int(por_pagina or 10)
    except (TypeError, ValueError):
        raise ValueError("por_pagina debe ser entero")
    per_page = max(1, min(100, per_page))

    roles = for_user_roles or []
    is_dispatcher = "dispatcher" in roles

    query = WorkOrder.query.options(
        selectinload(WorkOrder.assigned_to),
        selectinload(WorkOrder.created_by),
    )
    # scoping: coordinador solo ve las que creo o asigno
    if is_dispatcher and for_user_id is not None:
        query = query.filter(
            (WorkOrder.created_by_id == for_user_id) | (WorkOrder.assigned_to_id == for_user_id)
        )

    if estado:
        query = query.filter(WorkOrder.status == estado)
    if tecnico_id is not None and tecnico_id != "":
        try:
            tid = int(tecnico_id)
        except (TypeError, ValueError):
            raise ValueError("tecnico_id debe ser entero")
        query = query.filter(WorkOrder.assigned_to_id == tid)
    if zona:
        query = query.filter(WorkOrder.zone == zona)
    if desde_dt is not None:
        query = query.filter(fecha_col >= desde_dt)
    if hasta_dt is not None:
        query = query.filter(fecha_col <= hasta_dt)

    # resumen con los mismos filtros
    count_query = WorkOrder.query
    if is_dispatcher and for_user_id is not None:
        count_query = count_query.filter(
            (WorkOrder.created_by_id == for_user_id) | (WorkOrder.assigned_to_id == for_user_id)
        )
    if estado:
        count_query = count_query.filter(WorkOrder.status == estado)
    if tecnico_id is not None and tecnico_id != "":
        count_query = count_query.filter(WorkOrder.assigned_to_id == int(tecnico_id))
    if zona:
        count_query = count_query.filter(WorkOrder.zone == zona)
    if desde_dt is not None:
        count_query = count_query.filter(fecha_col >= desde_dt)
    if hasta_dt is not None:
        count_query = count_query.filter(fecha_col <= hasta_dt)

    resumen = {st: 0 for st in ALL_STATUSES}
    for st, cnt in count_query.with_entities(WorkOrder.status, db.func.count(WorkOrder.id)).group_by(WorkOrder.status).all():
        if st in resumen:
            resumen[st] = cnt

    total = query.count()
    items = query.order_by(WorkOrder.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    filtros = {
        "estado": estado or None,
        "tecnico_id": int(tecnico_id) if (tecnico_id not in (None, "")) else None,
        "zona": zona or None,
        "desde": desde or None,
        "hasta": hasta or None,
        "campo_fecha": campo_fecha,
        "pagina": page,
        "por_pagina": per_page,
    }

    return {
        "resumen": resumen,
        "items": [o.to_dict() for o in items],
        "total": total,
        "page": page,
        "page_size": per_page,
        "filtros": filtros,
    }
