# -*- coding: utf-8 -*-
from datetime import datetime, timezone

import sqlalchemy as sa

from app.extensions import db

MOVEMENT_IN = "IN"
MOVEMENT_OUT = "OUT"
MOVEMENT_CONSUMPTION = "CONSUMPTION"

ALL_MOVEMENTS = [MOVEMENT_IN, MOVEMENT_OUT, MOVEMENT_CONSUMPTION]


class Material(db.Model):
    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    description = db.Column(db.String(250))
    unit = db.Column(db.String(20), nullable=False)
    current_stock = db.Column(db.Float, nullable=False, default=0)
    min_stock = db.Column(db.Float, nullable=False, default=0)
    unit_price = db.Column(db.Float, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "unit": self.unit,
            "current_stock": self.current_stock,
            "min_stock": self.min_stock,
            "unit_price": self.unit_price,
            "is_active": self.is_active,
        }


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    movement_type = db.Column(db.String(15), nullable=False)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    notes = db.Column(db.String(250))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    material = db.relationship("Material")
    user = db.relationship("User")
    work_order = db.relationship("WorkOrder")

    def to_dict(self):
        return {
            "id": self.id,
            "material": self.material.to_dict() if self.material else None,
            "quantity": self.quantity,
            "movement_type": self.movement_type,
            "work_order_id": self.work_order_id,
            "user": self.user.to_dict() if self.user else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TechnicianStock(db.Model):
    __tablename__ = "technician_stock"

    id = db.Column(db.Integer, primary_key=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("technician_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False, default=0)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    technician = db.relationship("TechnicianProfile")
    material = db.relationship("Material")

    def to_dict(self):
        return {
            "id": self.id,
            "technician_id": self.technician_id,
            "material_id": self.material_id,
            "material": self.material.to_dict() if self.material else None,
            "quantity": self.quantity,
        }


class MaterialRequest(db.Model):
    __tablename__ = "material_requests"

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False, index=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("technician_profiles.id", ondelete="NO ACTION"), nullable=True, index=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id", ondelete="NO ACTION"), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="pendiente")
    reason = db.Column(db.Text)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="NO ACTION"), nullable=True)
    approval_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    requester = db.relationship("User", foreign_keys=[requester_id])
    approver = db.relationship("User", foreign_keys=[approved_by_id])
    items = db.relationship("MaterialRequestItem", backref="request", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "requester_id": self.requester_id,
            "technician_id": self.technician_id,
            "work_order_id": self.work_order_id,
            "status": self.status,
            "reason": self.reason,
            "approved_by_id": self.approved_by_id,
            "approval_reason": self.approval_reason,
            "items": [i.to_dict() for i in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MaterialRequestItem(db.Model):
    __tablename__ = "material_request_items"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("material_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id", ondelete="NO ACTION"), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)

    material = db.relationship("Material")

    def to_dict(self):
        return {
            "id": self.id,
            "request_id": self.request_id,
            "material_id": self.material_id,
            "material": self.material.to_dict() if self.material else None,
            "quantity": self.quantity,
        }


class TechnicianProfile(db.Model):
    __tablename__ = "technician_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    specialty = db.Column(db.String(80))
    specialty_code = db.Column(db.String(60), db.ForeignKey("specialties.code", ondelete="NO ACTION"))
    legacy_zone = db.Column(db.String(250))
    document_type = db.Column(db.String(20))
    document_number = db.Column(db.String(40))
    document = db.Column(db.String(40))
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, server_default=sa.text("1"))
    open_orders = db.Column(db.Integer, default=0, nullable=False, server_default=sa.text("0"))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user": self.user.to_dict() if self.user else None,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "name": f"{self.first_name or ''} {self.last_name or ''}".strip() or (self.user.username if self.user else ''),
            "phone": self.phone,
            "email": self.email,
            "specialty": self.specialty,
            "zones": self.legacy_zone,
            "legacy_zone": self.legacy_zone,
            "document": self.document,
            "is_available": self.is_available,
            "is_active": self.is_active,
            "open_orders": self.open_orders,
            "coverage": [
                {
                    "id": c.id,
                    "city_id": c.city_id,
                    "city_label": (c.city.label() if c.city else None),
                    "zone_id": c.zone_id,
                    "zone_name": (c.zone.name if c.zone else None),
                    "is_primary": c.is_primary,
                }
                for c in (getattr(self, "coverages", None) or [])
            ],
        }

