from datetime import datetime, timezone

import sqlalchemy as sa

from app.extensions import db

STATUS_PENDING = "pending"
STATUS_ASSIGNED = "assigned"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_CLOSED = "closed"
STATUS_CANCELLED = "cancelled"

ALL_STATUSES = [
    STATUS_PENDING,
    STATUS_ASSIGNED,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_CLOSED,
    STATUS_CANCELLED,
]

TRANSITIONS = {
    STATUS_PENDING: {STATUS_ASSIGNED, STATUS_CANCELLED},
    STATUS_ASSIGNED: {STATUS_IN_PROGRESS, STATUS_CANCELLED},
    STATUS_IN_PROGRESS: {STATUS_COMPLETED},
    STATUS_COMPLETED: {STATUS_CLOSED},
    STATUS_CLOSED: set(),
    STATUS_CANCELLED: set(),
}


class WorkOrder(db.Model):
    __tablename__ = "work_orders"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)
    priority = db.Column(db.String(10), nullable=False, default="medium")
    customer_name = db.Column(db.String(120))
    customer_phone = db.Column(db.String(30))
    address = db.Column(db.String(250))
    zone = db.Column(db.String(60), index=True)
    legacy_zone = db.Column(db.String(60), index=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id", ondelete="RESTRICT"), index=True)
    zone_id = db.Column(db.Integer, db.ForeignKey("zones.id", ondelete="RESTRICT"), index=True)
    installation_type = db.Column(db.String(80))
    installation_type_code = db.Column(db.String(60), db.ForeignKey("installation_types.code", ondelete="RESTRICT"))
    scheduled_at = db.Column(db.DateTime(timezone=True), index=True)
    scheduled_end = db.Column(db.DateTime(timezone=True))
    schedule_notes = db.Column(db.Text)
    version = db.Column(db.Integer, nullable=False, default=0, server_default=sa.text("0"))
    cancel_reason = db.Column(db.Text)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        db.CheckConstraint("status IN ('pending','assigned','in_progress','completed','closed','cancelled')", name="ck_wo_status"),
        db.CheckConstraint("priority IN ('high','medium','low')", name="ck_wo_priority"),
    )

    city = db.relationship("City", foreign_keys=[city_id])
    service_zone = db.relationship("Zone", foreign_keys=[zone_id])
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    history = db.relationship("WorkOrderStatusHistory", backref="work_order", lazy="selectin", order_by="WorkOrderStatusHistory.created_at")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "address": self.address,
            "zone": self.zone,
            "legacy_zone": self.legacy_zone,
            "city_id": self.city_id,
            "zone_id": self.zone_id,
            "installation_type": self.installation_type,
            "installation_type_code": self.installation_type_code,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "scheduled_end": self.scheduled_end.isoformat() if self.scheduled_end else None,
            "version": self.version,
            "cancel_reason": self.cancel_reason,
            "assigned_to": self.assigned_to.to_dict() if self.assigned_to else None,
            "created_by": self.created_by.to_dict() if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class WorkOrderStatusHistory(db.Model):
    __tablename__ = "work_order_status_history"

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"), nullable=False, index=True)
    from_status = db.Column(db.String(20), nullable=False)
    to_status = db.Column(db.String(20), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    changed_by = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "changed_by": self.changed_by.to_dict() if self.changed_by else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
