# -*- coding: utf-8 -*-
from app.extensions import db
from app.materials.models import Material, StockMovement, TechnicianProfile, MOVEMENT_IN, MOVEMENT_OUT


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

