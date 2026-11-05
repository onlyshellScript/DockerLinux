# -*- coding: utf-8 -*-
from app.extensions import db
from app.common.normalize import normalize_text
from app.materials.models import (
    Material, StockMovement, TechnicianProfile, TechnicianStock,
    MOVEMENT_IN, MOVEMENT_OUT, MOVEMENT_CONSUMPTION, MOVEMENT_ADJUSTMENT, MOVEMENT_RETURN,
    MOVEMENT_TRANSFER_OUT, ALL_MOVEMENTS,
)
from app.settings.models import OperationalSettings
from app.settings import service as settings_service


def _critical_threshold():
    op = OperationalSettings.query.first()
    if not op:
        op = OperationalSettings()
        db.session.add(op)
        db.session.commit()
    return float(op.stock_critical_threshold or 0.5)


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


def _material_code_exists(code, exclude_id=None):
    q = Material.query.filter(db.func.lower(Material.code) == code.lower())
    if exclude_id:
        q = q.filter(Material.id != exclude_id)
    return q.first() is not None


def create_material(data):
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip()
    unit = (data.get("unit") or "").strip()
    if not name or not code or not unit:
        raise ValueError("name, code and unit required")
    norm_code = normalize_text(code)
    if _material_code_exists(code):
        raise ValueError("duplicate_code")
    initial_stock = float(data.get("current_stock", data.get("initial_stock", 0)) or 0)
    if initial_stock < 0:
        raise ValueError("invalid_stock")
    m = Material(
        name=name,
        code=code,
        description=data.get("description"),
        unit=unit,
        current_stock=0,
        min_stock=data.get("min_stock", 0),
        unit_price=data.get("unit_price", 0),
        is_active=data.get("is_active", True),
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


def _apply_movement(mat, quantity, movement_type):
    qty = float(quantity)
    if movement_type in (MOVEMENT_IN, MOVEMENT_RETURN, MOVEMENT_ADJUSTMENT):
        # adjustment sets? We treat positive adjustment as increase; negative not allowed here.
        mat.current_stock = float(mat.current_stock or 0) + qty
    elif movement_type in (MOVEMENT_OUT, MOVEMENT_CONSUMPTION, MOVEMENT_TRANSFER_OUT):
        mat.current_stock = float(mat.current_stock or 0) - qty
    else:
        raise ValueError("invalid movement_type")


def list_materials(q=None, status=None, unit=None, is_active=None, page=1, page_size=20, sort="name", order="asc"):
    query = Material.query
    if is_active is not None:
        query = query.filter_by(is_active=is_active)
    if unit:
        query = query.filter(Material.unit == unit)
    if q:
        nq = normalize_text(q)
        query = query.filter(db.or_(
            db.func.lower(Material.name).contains(nq),
            db.func.lower(Material.code).contains(nq),
        ))
    # status filter applied after computing; we filter in python for derived status
    all_items = query.all()
    # compute derived status
    enriched = []
    for m in all_items:
        st = material_status(m.current_stock, m.min_stock)
        if status and st != status:
            continue
        enriched.append((m, st))
    # sort
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


def get_material(mat_id):
    return db.session.get(Material, mat_id)


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
    for field in ("name", "description", "unit", "min_stock", "unit_price", "is_active"):
        if field in data:
            setattr(m, field, data[field])
    db.session.commit()
    return m


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
    m = Material.query.filter_by(id=mat_id).with_for_update().first()
    if not m:
        return None, "not_found"
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


def get_movements(mat_id=None, work_order_id=None):
    q = StockMovement.query
    if mat_id:
        q = q.filter_by(material_id=mat_id)
    if work_order_id:
        q = q.filter_by(work_order_id=work_order_id)
    return q.order_by(StockMovement.created_at.desc()).all()


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


def list_profiles(is_available=None):
    q = TechnicianProfile.query
    if is_available is not None:
        q = q.filter_by(is_available=is_available)
    return q.all()


def get_profile(profile_id):
    return db.session.get(TechnicianProfile, profile_id)


def update_profile(profile_id, data):
    p = db.session.get(TechnicianProfile, profile_id)
    if not p:
        return None
    for field in ("phone", "specialty", "is_available"):
        if field in data:
            setattr(p, field, data[field])
    db.session.commit()
    return p




def get_technician_stock(technician_id):
    return TechnicianStock.query.filter_by(technician_id=technician_id).all()


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
    # lock rows
    m = Material.query.filter_by(id=material_id).with_for_update().first()
    ts = TechnicianStock.query.filter_by(technician_id=technician_id, material_id=material_id).with_for_update().first()
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


def consume_for_order(material_id, technician_id, quantity, work_order_id, user_id, notes=None):
    if quantity <= 0:
        return None, "invalid_quantity"
    ts = TechnicianStock.query.filter_by(technician_id=technician_id, material_id=material_id).with_for_update().first()
    if not ts or ts.quantity < quantity:
        return None, "insufficient_stock"
    ts.quantity -= quantity
    mv = StockMovement(material_id=material_id, quantity=quantity, movement_type=MOVEMENT_CONSUMPTION,
                       work_order_id=work_order_id, user_id=user_id, notes=notes)
    db.session.add(mv)
    db.session.commit()
    return mv, None

from app.materials.models import MaterialRequest, MaterialRequestItem


def create_material_request(data, user_id):
    req = MaterialRequest(
        requester_id=user_id,
        technician_id=data.get("technician_id"),
        work_order_id=data.get("work_order_id"),
        reason=data.get("reason"),
        status="pendiente",
    )
    db.session.add(req)
    db.session.flush()
    for it in data.get("items", []):
        db.session.add(MaterialRequestItem(request_id=req.id, material_id=it["material_id"], quantity=it["quantity"]))
    db.session.commit()
    return req


def approve_request(req_id, user_id, reason=None):
    req = MaterialRequest.query.filter_by(id=req_id).with_for_update().first()
    if not req or req.status != "pendiente":
        return None, "invalid_state"
    req.status = "autorizada"
    req.approved_by_id = user_id
    req.approval_reason = reason
    db.session.commit()
    return req, None


def reject_request(req_id, user_id, reason=None):
    req = MaterialRequest.query.filter_by(id=req_id).with_for_update().first()
    if not req or req.status != "pendiente":
        return None, "invalid_state"
    req.status = "rechazada"
    req.approved_by_id = user_id
    req.approval_reason = reason
    db.session.commit()
    return req, None


def deliver_request(req_id, user_id):
    req = MaterialRequest.query.filter_by(id=req_id).with_for_update().first()
    if not req or req.status != "autorizada":
        return None, "invalid_state"
    # lock materials and transfer
    for it in req.items:
        m = Material.query.filter_by(id=it.material_id).with_for_update().first()
        if not m or m.current_stock < it.quantity:
            return None, "insufficient_stock"
        m.current_stock -= it.quantity
        if req.technician_id:
            ts = TechnicianStock.query.filter_by(technician_id=req.technician_id, material_id=it.material_id).with_for_update().first()
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


def list_requests(status=None):
    q = MaterialRequest.query
    if status:
        q = q.filter_by(status=status)
    return q.order_by(MaterialRequest.created_at.desc()).all()
