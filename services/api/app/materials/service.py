from sqlalchemy import text
# -*- coding: utf-8 -*-
from app.extensions import db
from app.common.normalize import normalize_text, normalize_upper
from app.materials.models import (
    Material, StockMovement, TechnicianProfile, TechnicianStock,
    MOVEMENT_IN, MOVEMENT_OUT, MOVEMENT_CONSUMPTION, MOVEMENT_ADJUSTMENT, MOVEMENT_RETURN,
    MOVEMENT_TRANSFER_OUT, ALL_MOVEMENTS,
    MaterialRequest, MaterialRequestItem, MaterialRequestEvent, MaterialRequestDelivery,
    MaterialRequestDeliveryItem, MaterialRequestOperation,
)
from app.settings.models import OperationalSettings
from app.settings import service as settings_service



# Gestiona lock row; recibe table, key_col, key_val, extra, params; interactua con la base de datos; devuelve el valor correspondiente.
def _lock_row(table, key_col=None, key_val=None, extra=None, params=None):
    bind = db.session.get_bind()
    dialect = getattr(bind, "dialect", None)
    name = getattr(dialect, "name", "")
    if name != "mssql":
        return
    if key_col and key_val is not None:
        sql = f"SELECT 1 FROM {table} WITH (UPDLOCK, HOLDLOCK) WHERE {key_col} = :v"
        db.session.execute(text(sql), {"v": key_val})
    elif extra:
        sql = f"SELECT 1 FROM {table} WITH (UPDLOCK, HOLDLOCK) WHERE {extra}"
        db.session.execute(text(sql), params or {})

# Gestiona critical threshold; recibe sin parametros; interactua con la base de datos; devuelve el valor correspondiente.
def _critical_threshold():
    op = OperationalSettings.query.first()
    if not op:
        op = OperationalSettings()
        db.session.add(op)
        db.session.commit()
    return float(op.stock_critical_threshold or 0.5)


# Gestiona material status; recibe stock, minimum; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def material_status(stock, minimum):
    stock = float(stock or 0)
    minimum = float(minimum or 0)
    threshold = _critical_threshold()
    if minimum <= 0:
        if stock <= 0:
            return "critical"
        return "ok"
    if stock <= 0 or stock <= minimum * threshold:
        return "critical"
    if stock <= minimum:
        return "low"
    return "ok"


# _material_code_exists: indica si ya existe un material con el codigo dado (case-insensitive), excluyendo un id opcional; entradas code, exclude_id; salida bool; lee la base de datos.
def _material_code_exists(code, exclude_id=None):
    q = Material.query.filter(db.func.lower(Material.code) == code.lower())
    if exclude_id:
        q = q.filter(Material.id != exclude_id)
    return q.first() is not None


# _material_name_exists(name, exclude_id): ya hay un material con el mismo nombre al normalizar mayúsculas, acentos y
# espacios ("Tornillo", "TORNILLO", " tornillo " son el mismo). Compara en la aplicación para no depender de la collation.
def _material_name_exists(name, exclude_id=None):
    target = normalize_text(name)
    if not target:
        return False
    q = db.session.query(Material.id, Material.name)
    if exclude_id:
        q = q.filter(Material.id != exclude_id)
    return any(normalize_text(n) == target for _, n in q.all())


# unit_allows_decimal: determina si el material admite cantidades decimales segun su unidad de catalogo o nombre de unidad; entrada material; salida bool; sin efectos secundarios.
def unit_allows_decimal(material):
    if getattr(material, "catalog_item", None) and getattr(material.catalog_item, "unit", None):
        return bool(material.catalog_item.unit.allows_decimal)
    unit = (material.unit or "").lower()
    return unit in ("m", "kg", "lt", "rollo", "metro", "kilogramo", "litro")


# Valida los datos y reglas de negocio; recibe value, allows; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def _validate_decimal(value, allows):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    if not allows:
        if abs(f - round(f)) > 1e-9:
            return False
    return True


# Crea el registro solicitado con los datos recibidos; recibe data; interactua con la base de datos; devuelve el valor correspondiente.
def create_material(data):
    catalog_item_id = data.get("catalog_item_id")
    if not catalog_item_id:
        raise ValueError("catalog_item_id required")
    try:
        catalog_item_id = int(catalog_item_id)
    except (TypeError, ValueError):
        raise ValueError("invalid catalog_item_id")
    from app.materials.models import MaterialCatalog
    ci = db.session.get(MaterialCatalog, catalog_item_id)
    if not ci or not ci.is_active:
        raise ValueError("catalog_item not found")

    existing = Material.query.filter_by(catalog_item_id=catalog_item_id).first()
    if existing:
        raise ValueError("already_inventoried")

    initial_stock = data.get("current_stock", data.get("initial_stock", 0))
    if initial_stock is None:
        initial_stock = 0
    try:
        initial_stock = float(initial_stock)
    except (TypeError, ValueError):
        raise ValueError("invalid stock")
    if initial_stock < 0:
        raise ValueError("invalid stock")
    min_stock = data.get("min_stock", 0)
    try:
        min_stock = float(min_stock)
    except (TypeError, ValueError):
        raise ValueError("invalid min_stock")
    if min_stock < 0:
        raise ValueError("invalid min_stock")
    unit_price = data.get("unit_price", 0)
    try:
        from decimal import Decimal
        unit_price = Decimal(str(unit_price))
    except Exception:
        raise ValueError("invalid price")

    allows = bool(ci.unit.allows_decimal) if ci.unit else (ci.unit_id is not None)
    if not _validate_decimal(initial_stock, allows):
        raise ValueError("stock precision not allowed for unit")
    if not _validate_decimal(min_stock, allows):
        raise ValueError("min_stock precision not allowed for unit")

    m = Material(
        name=ci.name,
        code=ci.code,
        description=data.get("description") or ci.measure,
        unit=ci.unit.code if ci.unit else (data.get("unit") or "unidad"),
        current_stock=0,
        min_stock=min_stock,
        unit_price=unit_price,
        is_active=data.get("is_active", True),
        catalog_item_id=ci.id,
    )
    db.session.add(m)
    db.session.flush()
    if initial_stock > 0:
        mv = StockMovement(
            material_id=m.id,
            quantity=initial_stock,
            movement_type=MOVEMENT_ADJUSTMENT,
            user_id=data.get("user_id") or 1,
            notes="Saldo inicial",
        )
        db.session.add(mv)
        m.current_stock = initial_stock
    db.session.commit()
    return m


# Aplica la configuracion solicitada; recibe mat, quantity, movement_type; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def _apply_movement(mat, quantity, movement_type):
    qty = float(quantity)
    if movement_type in (MOVEMENT_IN, MOVEMENT_RETURN, MOVEMENT_ADJUSTMENT):
        # adjustment sets? We treat positive adjustment as increase; negative not allowed here.
        mat.current_stock = float(mat.current_stock or 0) + qty
    elif movement_type in (MOVEMENT_OUT, MOVEMENT_CONSUMPTION, MOVEMENT_TRANSFER_OUT):
        mat.current_stock = float(mat.current_stock or 0) - qty
    else:
        raise ValueError("invalid movement_type")


# Lista los registros que cumplen los filtros indicados; recibe q, status, unit, is_active, page, page_size, sort, order; interactua con la base de datos; devuelve el valor correspondiente.
def list_materials(q=None, status=None, unit=None, is_active=None, page=1, page_size=20, sort="name", order="asc"):
    query = Material.query
    if is_active is not None:
        query = query.filter_by(is_active=is_active)
    if unit:
        query = query.filter(Material.unit == normalize_upper(unit))
    # status filter applied after computing; we filter in python for derived status
    all_items = query.all()
    if q:
        # Búsqueda sin distinguir mayúsculas ni acentos ("tuberia" encuentra "TUBERÍA"), igual en SQL Server y SQLite.
        nq = normalize_text(q)
        all_items = [m for m in all_items if nq in (normalize_text(m.name) or "") or nq in (normalize_text(m.code) or "")]
    enriched = []
    for m in all_items:
        st = material_status(m.current_stock, m.min_stock)
        if status and st != status:
            continue
        enriched.append((m, st))
    reverse = (order or "asc").lower() == "desc"
    keymap = {
        "name": lambda x: (x[0].name or "").lower(),
        "code": lambda x: (x[0].code or "").lower(),
        "stock": lambda x: float(x[0].current_stock or 0),
        "status": lambda x: x[1],
    }
    enriched.sort(key=keymap.get(sort, keymap["name"]), reverse=reverse)
    total = len(enriched)
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 20)))
    start = (page - 1) * page_size
    page_items = enriched[start:start + page_size]
    # counts over all active? over filtered base (q/unit/active) but before status
    counts = {"total": len(all_items), "ok": 0, "low": 0, "critical": 0}
    for m in all_items:
        st = material_status(m.current_stock, m.min_stock)
        counts[st if st in ("ok", "low", "critical") else "ok"] += 1
    total_value = sum(float(m.current_stock or 0) * float(m.unit_price or 0) for m, _ in enriched if False) 
    total_value = sum(float(m.current_stock or 0) * float(m.unit_price or 0) for m in all_items)
    return {
        "items": [{"material": m, "status": st} for m, st in page_items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "counts": counts,
        "total_value": total_value,
    }


# get_material: obtiene un material por su id; entrada mat_id; salida Material o None; lee la base de datos.
def get_material(mat_id):
    return db.session.get(Material, mat_id)


# Actualiza los campos indicados del registro; recibe mat_id, data; interactua con la base de datos; devuelve el valor correspondiente.
def update_material(mat_id, data):
    m = db.session.get(Material, mat_id)
    if not m:
        return None
    if "code" in data and data["code"] is not None:
        new_code = str(data["code"]).strip()
        if new_code and new_code != m.code:
            if _material_code_exists(new_code, exclude_id=m.id):
                raise ValueError("duplicate_code")
            m.code = new_code
    if "catalog_item_id" in data:
        new_cid = data["catalog_item_id"]
        if new_cid is None:
            m.catalog_item_id = None
        else:
            try:
                new_cid = int(new_cid)
            except (TypeError, ValueError):
                raise ValueError("invalid catalog_item_id")
            from app.materials.models import MaterialCatalog
            ci = db.session.get(MaterialCatalog, new_cid)
            if not ci:
                raise ValueError("catalog_item not found")
            dup = Material.query.filter(Material.catalog_item_id == new_cid, Material.id != m.id).first()
            if dup:
                raise ValueError("already_inventoried")
            m.catalog_item_id = new_cid
            # sync name/code/unit from catalog
            m.name = ci.name
            m.code = ci.code
            m.unit = ci.unit.code if ci.unit else m.unit
    if "name" in data and data["name"] is not None:
        if _material_name_exists(data["name"], exclude_id=m.id):
            raise ValueError("duplicate_name")
    for field in ("name", "description", "unit", "min_stock", "unit_price", "is_active"):
        if field in data:
            setattr(m, field, data[field])
    db.session.commit()
    return m


# Gestiona enqueue stock alert; recibe material, old_status, new_status, user_id; interactua con la base de datos; devuelve el valor correspondiente.
def _enqueue_stock_alert(material, old_status, new_status, user_id):
    if new_status not in ("low", "critical"):
        return
    if old_status == new_status:
        return
    # one notification per crossing
    from app.identity.models import User
    from app.notifications.service import enqueue_notification
    recipients = User.query.filter(User.roles.any(name__in=["admin", "dispatcher"]) if False else True).all()
    # filter by role names
    target_users = []
    for u in User.query.all():
        role_names = [r.name for r in getattr(u, "roles", [])]
        if "admin" in role_names or "dispatcher" in role_names:
            target_users.append(u)
    subject = f"Stock {'critico' if new_status == 'critical' else 'bajo'}: {material.name}"
    message = f"El material {material.name} ({material.code}) paso a estado {new_status}. Stock actual: {material.current_stock} {material.unit}."
    for u in target_users:
        if getattr(u, "email", None):
            try:
                enqueue_notification(u.id, "email", u.email, subject, message)
            except Exception:
                pass


# Gestiona register movement; recibe mat_id, quantity, movement_type, user_id, work_order_id, notes; interactua con la base de datos; devuelve el valor correspondiente.
def register_movement(mat_id, quantity, movement_type, user_id, work_order_id=None, notes=None):
    quantity = float(quantity)
    if movement_type == MOVEMENT_ADJUSTMENT:
        if quantity == 0:
            return None, "invalid_quantity"
    else:
        if quantity <= 0:
            return None, "invalid_quantity"
    if movement_type not in ALL_MOVEMENTS:
        return None, "invalid_type"
    _lock_row("Materiales", "IdMaterial", mat_id)
    m = db.session.get(Material, mat_id)
    if not m:
        return None, "not_found"
    if not _validate_decimal(quantity, unit_allows_decimal(m)):
        return None, "invalid_quantity_precision"
    old_status = material_status(m.current_stock, m.min_stock)
    if movement_type == MOVEMENT_IN:
        m.current_stock = float(m.current_stock or 0) + quantity
    elif movement_type == MOVEMENT_RETURN:
        m.current_stock = float(m.current_stock or 0) + quantity
    elif movement_type == MOVEMENT_OUT:
        if float(m.current_stock or 0) < quantity:
            return None, "insufficient_stock"
        m.current_stock = float(m.current_stock or 0) - quantity
    elif movement_type == MOVEMENT_CONSUMPTION:
        if float(m.current_stock or 0) < quantity:
            return None, "insufficient_stock"
        m.current_stock = float(m.current_stock or 0) - quantity
    elif movement_type == MOVEMENT_ADJUSTMENT:
        new_stock = float(m.current_stock or 0) + quantity
        if new_stock < 0:
            return None, "insufficient_stock"
        m.current_stock = new_stock
    else:
        return None, "invalid_type"
    new_status = material_status(m.current_stock, m.min_stock)
    mv = StockMovement(
        material_id=mat_id,
        quantity=quantity,
        movement_type=movement_type,
        work_order_id=work_order_id,
        user_id=user_id,
        notes=notes,
    )
    db.session.add(mv)
    db.session.commit()
    _enqueue_stock_alert(m, old_status, new_status, user_id)
    return mv, None


# Obtiene un registro por su identificador; recibe mat_id, work_order_id; interactua con la base de datos; devuelve el valor correspondiente.
def get_movements(mat_id=None, work_order_id=None):
    q = StockMovement.query
    if mat_id:
        q = q.filter_by(material_id=mat_id)
    if work_order_id:
        q = q.filter_by(work_order_id=work_order_id)
    return q.order_by(StockMovement.created_at.desc()).all()


# Crea el registro solicitado con los datos recibidos; recibe data; interactua con la base de datos; devuelve el valor correspondiente.
def create_profile(data):
    p = TechnicianProfile(
        user_id=data["user_id"],
        phone=data.get("phone"),
        specialty=data.get("specialty"),
        is_available=data.get("is_available", True),
    )
    db.session.add(p)
    db.session.commit()
    return p


# list_profiles: lista perfiles de tecnico, filtrando por disponibilidad si se indica; entrada is_available opcional; salida list; lee la base de datos.
def list_profiles(is_available=None):
    q = TechnicianProfile.query
    if is_available is not None:
        q = q.filter_by(is_available=is_available)
    return q.all()


# get_profile: obtiene un perfil de tecnico por su id; entrada profile_id; salida TechnicianProfile o None; lee la base de datos.
def get_profile(profile_id):
    return db.session.get(TechnicianProfile, profile_id)


# Actualiza los campos indicados del registro; recibe profile_id, data; interactua con la base de datos; devuelve el valor correspondiente.
def update_profile(profile_id, data):
    p = db.session.get(TechnicianProfile, profile_id)
    if not p:
        return None
    for field in ("phone", "specialty", "is_available"):
        if field in data:
            setattr(p, field, data[field])
    db.session.commit()
    return p




# get_technician_stock: lista el stock asignado a un tecnico; entrada technician_id; salida list; lee la base de datos.
def get_technician_stock(technician_id):
    return TechnicianStock.query.filter_by(technician_id=technician_id).all()


# Gestiona transfer stock; recibe material_id, technician_id, quantity, user_id, notes; interactua con la base de datos; devuelve el valor correspondiente.
def transfer_stock(material_id, technician_id, quantity, user_id, notes=None):
    if quantity <= 0:
        return None, "invalid_quantity"
    m = db.session.get(Material, material_id)
    if not m:
        return None, "material_not_found"
    from app.materials.models import TechnicianProfile
    prof = db.session.get(TechnicianProfile, technician_id)
    if not prof:
        return None, "technician_not_found"
    _lock_row("Materiales", "IdMaterial", material_id)
    m = db.session.get(Material, material_id)
    _lock_row("StockTecnico", None, None, extra="IdTecnico = :t AND IdMaterial = :m", params={"t": technician_id, "m": material_id})
    ts = TechnicianStock.query.filter_by(technician_id=technician_id, material_id=material_id).first()
    if m.current_stock < quantity:
        return None, "insufficient_stock"
    m.current_stock -= quantity
    if not ts:
        ts = TechnicianStock(technician_id=technician_id, material_id=material_id, quantity=0)
        db.session.add(ts)
        db.session.flush()
    ts.quantity += quantity
    mv = StockMovement(material_id=material_id, quantity=quantity, movement_type="TRANSFER_OUT",
                       user_id=user_id, notes=notes or f"Transferencia a tecnico {technician_id}")
    db.session.add(mv)
    db.session.commit()
    return {"material": m, "technician_stock": ts}, None


# Gestiona consume for order; recibe material_id, technician_id, quantity, work_order_id, user_id, notes; interactua con la base de datos; devuelve el valor correspondiente.
def consume_for_order(material_id, technician_id, quantity, work_order_id, user_id, notes=None):
    if quantity <= 0:
        return None, "invalid_quantity"
    _lock_row("StockTecnico", None, None, extra="IdTecnico = :t AND IdMaterial = :m", params={"t": technician_id, "m": material_id})
    ts = TechnicianStock.query.filter_by(technician_id=technician_id, material_id=material_id).first()
    if not ts or ts.quantity < quantity:
        return None, "insufficient_stock"
    ts.quantity -= quantity
    mv = StockMovement(material_id=material_id, quantity=quantity, movement_type=MOVEMENT_CONSUMPTION,
                       work_order_id=work_order_id, user_id=user_id, notes=notes)
    db.session.add(mv)
    db.session.commit()
    return mv, None

from app.materials.models import MaterialRequest, MaterialRequestItem


# Crea el registro solicitado con los datos recibidos; recibe data, user_id; interactua con la base de datos; devuelve el valor correspondiente.
def create_material_request(data, user_id):
    req = MaterialRequest(
        requester_id=user_id,
        technician_id=data.get("technician_id"),
        work_order_id=data.get("work_order_id"),
        reason=data.get("reason"),
        status="SUBMITTED",
    )
    db.session.add(req)
    db.session.flush()
    for it in data.get("items", []):
        db.session.add(MaterialRequestItem(request_id=req.id, material_id=it["material_id"], quantity=it["quantity"],
                                          quantity_requested=it["quantity"]))
    db.session.commit()
    return req


# Gestiona approve request; recibe req_id, user_id, reason; interactua con la base de datos; devuelve el valor correspondiente.
def approve_request(req_id, user_id, reason=None):
    req = MaterialRequest.query.filter_by(id=req_id).with_for_update().first()
    if not req or req.status != "pendiente":
        return None, "invalid_state"
    req.status = "autorizada"
    req.approved_by_id = user_id
    req.approval_reason = reason
    db.session.commit()
    return req, None


# Gestiona reject request; recibe req_id, user_id, reason; interactua con la base de datos; devuelve el valor correspondiente.
def reject_request(req_id, user_id, reason=None):
    req = MaterialRequest.query.filter_by(id=req_id).with_for_update().first()
    if not req or req.status != "pendiente":
        return None, "invalid_state"
    req.status = "rechazada"
    req.approved_by_id = user_id
    req.approval_reason = reason
    db.session.commit()
    return req, None


# Gestiona deliver request; recibe req_id, user_id; interactua con la base de datos; devuelve el valor correspondiente.
def deliver_request(req_id, user_id):
    req = MaterialRequest.query.filter_by(id=req_id).with_for_update().first()
    if not req or req.status != "autorizada":
        return None, "invalid_state"
    # lock materials and transfer
    for it in req.items:
        _lock_row("Materiales", "IdMaterial", it.material_id)
        m = db.session.get(Material, it.material_id)
        if not m or m.current_stock < it.quantity:
            return None, "insufficient_stock"
        m.current_stock -= it.quantity
        if req.technician_id:
            _lock_row("StockTecnico", None, None, extra="IdTecnico = :t AND IdMaterial = :m", params={"t": req.technician_id, "m": it.material_id})
            ts = TechnicianStock.query.filter_by(technician_id=req.technician_id, material_id=it.material_id).first()
            if not ts:
                ts = TechnicianStock(technician_id=req.technician_id, material_id=it.material_id, quantity=0)
                db.session.add(ts)
                db.session.flush()
            ts.quantity += it.quantity
        mv = StockMovement(material_id=it.material_id, quantity=it.quantity, movement_type="TRANSFER_OUT",
                           work_order_id=req.work_order_id, user_id=user_id, notes=f"Entrega solicitud {req.id}")
        db.session.add(mv)
    req.status = "entregada"
    db.session.commit()
    return req, None


# list_requests: lista solicitudes de material, filtrando por estado si se indica, ordenadas por fecha descendente; entrada status opcional; salida list; lee la base de datos.
def list_requests(status=None):
    q = MaterialRequest.query
    if status:
        q = q.filter_by(status=status)
    return q.order_by(MaterialRequest.created_at.desc()).all()


# ---- Material request workflow (Fase 6.2) ----

VALID_STATUSES = ["DRAFT", "SUBMITTED", "APPROVED", "PARTIALLY_APPROVED", "REJECTED",
                  "PARTIALLY_DELIVERED", "DELIVERED", "CANCELLED"]
TERMINAL = {"REJECTED", "CANCELLED", "DELIVERED"}


# Aplica la transicion de estado solicitada; recibe req, new_status, actor_id, action, payload; interactua con la base de datos; devuelve el valor correspondiente.
def _transition(req, new_status, actor_id, action, payload=None):
    old = req.status
    req.status = new_status
    req.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    ev = MaterialRequestEvent(request_id=req.id, actor_id=actor_id, action=action,
                             from_status=old, to_status=new_status,
                             payload=__import__("json").dumps(payload) if payload is not None else None)
    db.session.add(ev)


# _get_request: obtiene una solicitud de material por id con bloqueo pesimista (with_for_update); entrada req_id; salida MaterialRequest o None; lee la base de datos.
def _get_request(req_id):
    # Bloqueo pesimista real; SQLite lo ignora, se valida en SQL Server (ver DECISIONES PENDIENTES).
    return MaterialRequest.query.filter_by(id=req_id).with_for_update().first()


# Crea el registro solicitado con los datos recibidos; recibe data, user_id, operation_id; interactua con la base de datos; devuelve el valor correspondiente.
def create_request(data, user_id, operation_id=None):
    if operation_id:
        op = MaterialRequestOperation.query.filter_by(operation_id=operation_id).first()
        if op:
            if op.result:
                import json
                try:
                    return json.loads(op.result), None
                except Exception:
                    pass
            # same key different payload -> conflict handled by caller; here treat as conflict
            return None, "duplicate_operation"
    items = data.get("items") or []
    if not items:
        return None, "no_items"
    from app.materials.models import Material
    for it in items:
        m = db.session.get(Material, it.get("material_id"))
        if not m or not m.is_active:
            return None, "invalid_material"
        q = float(it.get("quantity", 0))
        if q <= 0:
            return None, "invalid_quantity"
    draft = bool(data.get("draft", False))
    req = MaterialRequest(
        requester_id=user_id,
        technician_id=data.get("technician_id"),
        work_order_id=data.get("work_order_id"),
        reason=data.get("reason"),
        status="DRAFT" if draft else "SUBMITTED",
        client_operation_id=operation_id,
    )
    db.session.add(req)
    db.session.flush()
    for it in items:
        db.session.add(MaterialRequestItem(
            request_id=req.id,
            material_id=it["material_id"],
            quantity=float(it["quantity"]),
            quantity_requested=float(it["quantity"]),
        ))
    if not draft:
        _transition(req, "SUBMITTED", user_id, "submit", {"items": items})
    if operation_id:
        import json
        oprec = MaterialRequestOperation(operation_id=operation_id, operation_type="create",
                                        actor_id=user_id, request_id=req.id,
                                        result=json.dumps({"id": req.id}))
        db.session.add(oprec)
    db.session.commit()
    return req, None


# Actualiza los campos indicados del registro; recibe req_id, data, user_id, roles; interactua con la base de datos; devuelve el valor correspondiente.
def update_request(req_id, data, user_id, roles):
    req = db.session.get(MaterialRequest, req_id)
    if not req:
        return None, "not_found"
    if req.status != "DRAFT":
        return None, "invalid_state"
    if "admin" not in roles and "dispatcher" not in roles and req.requester_id != user_id:
        return None, "forbidden"
    if "reason" in data:
        req.reason = data.get("reason")
    if "technician_id" in data:
        req.technician_id = data.get("technician_id")
    if "work_order_id" in data:
        req.work_order_id = data.get("work_order_id")
    if "items" in data:
        MaterialRequestItem.query.filter_by(request_id=req.id).delete()
        for it in (data.get("items") or []):
            from app.materials.models import Material
            m = db.session.get(Material, it.get("material_id"))
            if not m or not m.is_active:
                return None, "invalid_material"
            q = float(it.get("quantity", 0))
            if q <= 0:
                return None, "invalid_quantity"
            db.session.add(MaterialRequestItem(request_id=req.id, material_id=it["material_id"],
                                             quantity=q, quantity_requested=q))
    db.session.commit()
    return req, None


# Gestiona submit request; recibe req_id, user_id, roles, operation_id; interactua con la base de datos; devuelve el valor correspondiente.
def submit_request(req_id, user_id, roles, operation_id=None):
    req = MaterialRequest.query.filter_by(id=req_id).with_for_update() if False else db.session.get(MaterialRequest, req_id)
    _lock_row("SolicitudesMaterial", "IdSolicitud", req_id)
    req = db.session.get(MaterialRequest, req_id)
    if not req:
        return None, "not_found"
    if req.status != "DRAFT":
        return None, "invalid_state"
    if "admin" not in roles and "dispatcher" not in roles and req.requester_id != user_id:
        return None, "forbidden"
    if not req.items:
        return None, "no_items"
    _transition(req, "SUBMITTED", user_id, "submit")
    db.session.commit()
    return req, None


# Gestiona approve request; recibe req_id, user_id, roles, approvals, reason, operation_id; interactua con la base de datos; devuelve el valor correspondiente.
def approve_request(req_id, user_id, roles, approvals=None, reason=None, operation_id=None):
    if "admin" not in roles and "dispatcher" not in roles:
        return None, "forbidden"
    _lock_row("SolicitudesMaterial", "IdSolicitud", req_id)
    req = db.session.get(MaterialRequest, req_id)
    if not req:
        return None, "not_found"
    if req.status not in ("SUBMITTED", "APPROVED", "PARTIALLY_APPROVED"):
        return None, "invalid_state"
    approvals = approvals or []
    amap = {a.get("item_id"): a for a in approvals}
    for it in req.items:
        a = amap.get(it.id, {})
        qa = a.get("quantity_approved", it.quantity_requested)
        try:
            qa = float(qa)
        except (TypeError, ValueError):
            return None, "invalid_quantity"
        if qa < 0 or qa > it.quantity_requested:
            return None, "invalid_approved_quantity"
        it.quantity_approved = qa
    total_req = sum(i.quantity_requested for i in req.items)
    total_app = sum(i.quantity_approved for i in req.items)
    if total_app == 0:
        new_status = "REJECTED"
    elif total_app >= total_req:
        new_status = "APPROVED"
    else:
        new_status = "PARTIALLY_APPROVED"
    if reason:
        req.approval_reason = reason
    req.approved_by_id = user_id
    _transition(req, new_status, user_id, "approve", {"approvals": approvals})
    db.session.commit()
    return req, None


# Gestiona reject request; recibe req_id, user_id, roles, reason; interactua con la base de datos; devuelve el valor correspondiente.
def reject_request(req_id, user_id, roles, reason=None):
    if "admin" not in roles and "dispatcher" not in roles:
        return None, "forbidden"
    _lock_row("SolicitudesMaterial", "IdSolicitud", req_id)
    req = db.session.get(MaterialRequest, req_id)
    if not req:
        return None, "not_found"
    if req.status in TERMINAL:
        return None, "invalid_state"
    req.approved_by_id = user_id
    req.approval_reason = reason
    _transition(req, "REJECTED", user_id, "reject", {"reason": reason})
    db.session.commit()
    return req, None


# Gestiona idempotency check; recibe operation_id, operation_type, actor_id, payload; interactua con la base de datos; devuelve el valor correspondiente.
def _idempotency_check(operation_id, operation_type, actor_id, payload):
    if not operation_id:
        return None
    from app.materials.models import MaterialRequestOperation
    oprec = MaterialRequestOperation.query.filter_by(operation_id=operation_id).first()
    if oprec:
        if oprec.operation_type != operation_type or oprec.actor_id != actor_id:
            return "conflict"
        # same key: return stored result (caller should return)
        return "replay"
    return None


# Gestiona deliver request; recibe req_id, user_id, roles, deliveries, operation_id; interactua con la base de datos; devuelve el valor correspondiente.
def deliver_request(req_id, user_id, roles, deliveries=None, operation_id=None):
    if "admin" not in roles and "dispatcher" not in roles:
        return None, "forbidden"
    idem = _idempotency_check(operation_id, "deliver", user_id, deliveries)
    if idem == "conflict":
        return None, "idempotency_conflict"
    if idem == "replay":
        # return existing request without reprocessing
        req = db.session.get(MaterialRequest, req_id)
        return req, None

    _lock_row("SolicitudesMaterial", "IdSolicitud", req_id)
    req = db.session.get(MaterialRequest, req_id)
    if not req:
        return None, "not_found"
    if req.status not in ("APPROVED", "PARTIALLY_APPROVED", "PARTIALLY_DELIVERED"):
        return None, "invalid_state"
    deliveries = deliveries or []
    # map item_id -> qty
    dmap = {}
    for d in deliveries:
        dmap.setdefault(d.get("item_id"), 0)
        dmap[d.get("item_id")] += float(d.get("quantity_delivered", 0))

    # validate and lock materials
    for it in req.items:
        if it.id not in dmap:
            continue
        qty = dmap[it.id]
        if qty <= 0:
            continue
        pending = (it.quantity_approved or 0) - (it.quantity_delivered or 0)
        if qty > pending + 1e-9:
            return None, "exceeds_approved"
        _lock_row("Materiales", "IdMaterial", it.material_id)
        m = db.session.get(Material, it.material_id)
        if not m or float(m.current_stock or 0) < qty:
            return None, "insufficient_stock"
    delivery = MaterialRequestDelivery(request_id=req.id, actor_id=user_id, operation_id=operation_id)
    db.session.add(delivery)
    db.session.flush()
    for it in req.items:
        if it.id not in dmap:
            continue
        qty = dmap[it.id]
        if qty <= 0:
            continue
        _lock_row("Materiales", "IdMaterial", it.material_id)
        m = db.session.get(Material, it.material_id)
        m.current_stock = float(m.current_stock or 0) - qty
        if req.technician_id:
            _lock_row("StockTecnico", None, None, extra="IdTecnico = :t AND IdMaterial = :m", params={"t": req.technician_id, "m": it.material_id})
            ts = TechnicianStock.query.filter_by(technician_id=req.technician_id, material_id=it.material_id).first()
            if not ts:
                ts = TechnicianStock(technician_id=req.technician_id, material_id=it.material_id, quantity=0)
                db.session.add(ts)
                db.session.flush()
            ts.quantity = float(ts.quantity or 0) + qty
        mv = StockMovement(material_id=it.material_id, quantity=qty, movement_type="TRANSFER_OUT",
                           work_order_id=req.work_order_id, user_id=user_id,
                           notes=f"Entrega solicitud {req.id}")
        db.session.add(mv)
        db.session.flush()
        db.session.add(MaterialRequestDeliveryItem(delivery_id=delivery.id, request_item_id=it.id,
                                                  quantity_delivered=qty, movement_id=mv.id))
        it.quantity_delivered = float(it.quantity_delivered or 0) + qty
    total_app = sum(i.quantity_approved for i in req.items)
    total_del = sum(i.quantity_delivered for i in req.items)
    if total_del >= total_app - 1e-9 and total_app > 0:
        new_status = "DELIVERED"
    elif total_del > 0:
        new_status = "PARTIALLY_DELIVERED"
    else:
        new_status = req.status
    if new_status != req.status:
        _transition(req, new_status, user_id, "deliver")
    req.delivered_by_id = user_id
    if operation_id:
        import json
        oprec = MaterialRequestOperation(operation_id=operation_id, operation_type="deliver",
                                        actor_id=user_id, request_id=req.id,
                                        result=json.dumps({"id": req.id, "status": req.status}))
        db.session.add(oprec)
    db.session.commit()
    return req, None


# Gestiona cancel request; recibe req_id, user_id, roles, reason; interactua con la base de datos; devuelve el valor correspondiente.
def cancel_request(req_id, user_id, roles, reason=None):
    _lock_row("SolicitudesMaterial", "IdSolicitud", req_id)
    req = db.session.get(MaterialRequest, req_id)
    if not req:
        return None, "not_found"
    if req.status in ("DELIVERED", "CANCELLED", "REJECTED"):
        return None, "invalid_state"
    if "admin" not in roles and "dispatcher" not in roles and req.requester_id != user_id:
        return None, "forbidden"
    # if already delivered partially, cancel only pending; keep delivered
    _transition(req, "CANCELLED", user_id, "cancel", {"reason": reason})
    db.session.commit()
    return req, None


# Obtiene un registro por su identificador; recibe req_id, user_id, roles; interactua con la base de datos; devuelve el valor correspondiente.
def get_request(req_id, user_id, roles):
    req = db.session.get(MaterialRequest, req_id)
    if not req:
        return None
    if "admin" not in roles and "dispatcher" not in roles and req.requester_id != user_id:
        return None
    return req


# Lista los registros que cumplen los filtros indicados; recibe status, work_order_id, mine, user_id, roles, page, page_size; interactua con la base de datos; devuelve el valor correspondiente.
def list_requests_filtered(status=None, work_order_id=None, mine=False, user_id=None, roles=None, page=1, page_size=20):
    q = MaterialRequest.query
    if status:
        q = q.filter_by(status=status)
    if work_order_id:
        q = q.filter_by(work_order_id=work_order_id)
    if mine and user_id and "admin" not in (roles or []) and "dispatcher" not in (roles or []):
        q = q.filter_by(requester_id=user_id)
    q = q.order_by(MaterialRequest.created_at.desc())
    total = q.count()
    items = q.offset((page-1)*page_size).limit(page_size).all()
    return items, total


# list_request_events: lista los eventos (historial) de una solicitud de material ordenados por fecha; entrada req_id; salida list; lee la base de datos.
def list_request_events(req_id):
    return MaterialRequestEvent.query.filter_by(request_id=req_id).order_by(MaterialRequestEvent.created_at).all()
