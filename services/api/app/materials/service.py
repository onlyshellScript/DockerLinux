# -*- coding: utf-8 -*-
from app.extensions import db
from app.materials.models import Material, StockMovement, TechnicianProfile, TechnicianStock, MOVEMENT_IN, MOVEMENT_OUT


def create_material(data):
    m = Material(
        name=data["name"],
        description=data.get("description"),
        unit=data["unit"],
        current_stock=data.get("current_stock", 0),
        min_stock=data.get("min_stock", 0),
        unit_price=data.get("unit_price", 0),
    )
    db.session.add(m)
    db.session.commit()
    return m


def list_materials(is_active=None):
    q = Material.query
    if is_active is not None:
        q = q.filter_by(is_active=is_active)
    return q.order_by(Material.name).all()


def get_material(mat_id):
    return db.session.get(Material, mat_id)


def update_material(mat_id, data):
    m = db.session.get(Material, mat_id)
    if not m:
        return None
    for field in ("name", "description", "unit", "min_stock", "unit_price", "is_active"):
        if field in data:
            setattr(m, field, data[field])
    db.session.commit()
    return m


def register_movement(mat_id, quantity, movement_type, user_id, work_order_id=None, notes=None):
    m = db.session.get(Material, mat_id)
    if not m:
        return None, "not_found"
    if movement_type == MOVEMENT_IN:
        m.current_stock += quantity
    elif movement_type == MOVEMENT_OUT:
        if m.current_stock < quantity:
            return None, "insufficient_stock"
        m.current_stock -= quantity
    else:
        if m.current_stock < quantity:
            return None, "insufficient_stock"
        m.current_stock -= quantity
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
