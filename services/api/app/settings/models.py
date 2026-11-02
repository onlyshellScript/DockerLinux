from datetime import datetime, timezone

import sqlalchemy as sa

from app.extensions import db


class OrganizationSettings(db.Model):
    __tablename__ = "organization_settings"

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False, default="SIGOS")
    nit = db.Column(db.String(40))
    admin_email = db.Column(db.String(120), nullable=False, default="admin@sigos.local")
    contact_phone = db.Column(db.String(30))
    address = db.Column(db.String(250))
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id", ondelete="RESTRICT"))
    timezone = db.Column(db.String(60), nullable=False, default="America/Bogota")
    version = db.Column(db.Integer, nullable=False, default=0, server_default=sa.text("0"))
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    city = db.relationship("City")


class OperationalSettings(db.Model):
    __tablename__ = "operational_settings"

    id = db.Column(db.Integer, primary_key=True)
    work_days = db.Column(db.String(20), nullable=False, default="1,2,3,4,5")  # 1=Mon..7=Sun
    work_start = db.Column(db.String(5), nullable=False, default="07:00")
    work_end = db.Column(db.String(5), nullable=False, default="18:00")
    default_visit_duration = db.Column(db.Integer, nullable=False, default=60)
    max_visit_duration = db.Column(db.Integer, nullable=False, default=480)
    min_advance_hours = db.Column(db.Integer, nullable=False, default=0)
    travel_margin_minutes = db.Column(db.Integer, nullable=False, default=0)
    calendar_interval = db.Column(db.Integer, nullable=False, default=30)
    version = db.Column(db.Integer, nullable=False, default=0, server_default=sa.text("0"))
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.CheckConstraint("calendar_interval IN (15,30,60)", name="ck_op_interval"),
    )


class SecuritySettings(db.Model):
    __tablename__ = "security_settings"

    id = db.Column(db.Integer, primary_key=True)
    session_inactivity_minutes = db.Column(db.Integer, nullable=False, default=30)
    session_max_hours = db.Column(db.Integer, nullable=False, default=8)
    password_min_length = db.Column(db.Integer, nullable=False, default=10)
    password_history_count = db.Column(db.Integer, nullable=False, default=3)
    lock_attempts = db.Column(db.Integer, nullable=False, default=5)
    lock_minutes = db.Column(db.Integer, nullable=False, default=15)
    temp_password_validity_days = db.Column(db.Integer, nullable=False, default=7)
    version = db.Column(db.Integer, nullable=False, default=0, server_default=sa.text("0"))
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class NotificationSettings(db.Model):
    __tablename__ = "notification_settings"

    id = db.Column(db.Integer, primary_key=True)
    # organization preferences: JSON string of event->channels
    preferences = db.Column(db.Text, nullable=False, default="{}")
    version = db.Column(db.Integer, nullable=False, default=0, server_default=sa.text("0"))
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class UserNotificationPreference(db.Model):
    __tablename__ = "user_notification_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True)
    preferences = db.Column(db.Text, nullable=False, default="{}")
    version = db.Column(db.Integer, nullable=False, default=0, server_default=sa.text("0"))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    section = db.Column(db.String(40), nullable=False, index=True)
    field = db.Column(db.String(80))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    result = db.Column(db.String(20), nullable=False, default="applied")  # applied/rejected/confirmed
    request_id = db.Column(db.String(40))
    username = db.Column(db.String(80))

    __table_args__ = (
        db.Index("ix_audit_log_section_created", "section", "created_at"),
    )
