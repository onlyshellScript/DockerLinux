from datetime import datetime, timezone

import sqlalchemy as sa

from app.extensions import db


# OrganizationSettings: modelo de base de datos que representa la entidad OrganizationSettings.
class OrganizationSettings(db.Model):
    __tablename__ = "ConfiguracionOrganizacion"

    id = db.Column("IdConfiguracion", db.Integer, primary_key=True)
    company_name = db.Column("NombreEmpresa", db.String(150), nullable=False, default="SIGOS")
    nit = db.Column("Nit", db.String(40))
    admin_email = db.Column("CorreoAdmin", db.String(120), nullable=False, default="admin@sigos.local")
    contact_phone = db.Column("TelefonoContacto", db.String(30))
    address = db.Column("Direccion", db.String(250))
    city_id = db.Column("IdCiudad", db.Integer, db.ForeignKey("Ciudades.IdCiudad", ondelete="NO ACTION"))
    timezone = db.Column("ZonaHoraria", db.String(60), nullable=False, default="America/Bogota")
    version = db.Column("Version", db.Integer, nullable=False, default=0, server_default=sa.text("0"))
    updated_by_id = db.Column("IdActualizadoPor", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    updated_at = db.Column("ActualizadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    city = db.relationship("City")


# OperationalSettings: modelo de base de datos que representa la entidad OperationalSettings.
class OperationalSettings(db.Model):
    __tablename__ = "ConfiguracionOperativa"

    id = db.Column("IdConfiguracion", db.Integer, primary_key=True)
    work_days = db.Column("DiasLaborales", db.String(20), nullable=False, default="1,2,3,4,5")  # 1=Mon..7=Sun
    work_start = db.Column("HoraInicio", db.String(5), nullable=False, default="07:00")
    work_end = db.Column("HoraFin", db.String(5), nullable=False, default="18:00")
    default_visit_duration = db.Column("DuracionVisitaDefault", db.Integer, nullable=False, default=60)
    max_visit_duration = db.Column("DuracionVisitaMax", db.Integer, nullable=False, default=480)
    min_advance_hours = db.Column("HorasAntelacionMin", db.Integer, nullable=False, default=0)
    travel_margin_minutes = db.Column("MargenTrasladoMin", db.Integer, nullable=False, default=0)
    calendar_interval = db.Column("IntervaloCalendario", db.Integer, nullable=False, default=30)
    stock_critical_threshold = db.Column("UmbralStockCritico", db.Float, nullable=False, default=0.5)
    version = db.Column("Version", db.Integer, nullable=False, default=0, server_default=sa.text("0"))
    updated_by_id = db.Column("IdActualizadoPor", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    updated_at = db.Column("ActualizadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.CheckConstraint("IntervaloCalendario IN (15,30,60)", name="ck_op_interval"),
    )


# SecuritySettings: modelo de base de datos que representa la entidad SecuritySettings.
class SecuritySettings(db.Model):
    __tablename__ = "ConfiguracionSeguridad"

    id = db.Column("IdConfiguracion", db.Integer, primary_key=True)
    session_inactivity_minutes = db.Column("MinutosInactividadSesion", db.Integer, nullable=False, default=30)
    session_max_hours = db.Column("HorasMaxSesion", db.Integer, nullable=False, default=8)
    password_min_length = db.Column("LongitudMinContrasena", db.Integer, nullable=False, default=10)
    password_history_count = db.Column("HistorialContrasenas", db.Integer, nullable=False, default=3)
    lock_attempts = db.Column("IntentosBloqueo", db.Integer, nullable=False, default=5)
    lock_minutes = db.Column("MinutosBloqueo", db.Integer, nullable=False, default=15)
    temp_password_validity_days = db.Column("DiasVigenciaContrasenaTemporal", db.Integer, nullable=False, default=7)
    version = db.Column("Version", db.Integer, nullable=False, default=0, server_default=sa.text("0"))
    updated_by_id = db.Column("IdActualizadoPor", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    updated_at = db.Column("ActualizadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# NotificationSettings: modelo de base de datos que representa la entidad NotificationSettings.
class NotificationSettings(db.Model):
    __tablename__ = "ConfiguracionNotificaciones"

    id = db.Column("IdConfiguracion", db.Integer, primary_key=True)
    # organization preferences: JSON string of event->channels
    preferences = db.Column("Preferencias", db.Text, nullable=False, default="{}")
    version = db.Column("Version", db.Integer, nullable=False, default=0, server_default=sa.text("0"))
    updated_by_id = db.Column("IdActualizadoPor", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    updated_at = db.Column("ActualizadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# UserNotificationPreference: modelo de base de datos que representa la entidad UserNotificationPreference.
class UserNotificationPreference(db.Model):
    __tablename__ = "PreferenciasNotificacionUsuario"

    id = db.Column("IdPreferencia", db.Integer, primary_key=True)
    user_id = db.Column("IdUsuario", db.Integer, db.ForeignKey("Usuarios.IdUsuario", ondelete="NO ACTION"), nullable=False, unique=True)
    preferences = db.Column("Preferencias", db.Text, nullable=False, default="{}")
    version = db.Column("Version", db.Integer, nullable=False, default=0, server_default=sa.text("0"))
    updated_at = db.Column("ActualizadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# AuditLog: modelo de base de datos que representa la entidad AuditLog.
class AuditLog(db.Model):
    __tablename__ = "Auditoria"

    id = db.Column("IdAuditoria", db.Integer, primary_key=True)
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    user_id = db.Column("IdUsuario", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    section = db.Column("NombreTabla", db.String(40), nullable=False, index=True)
    field = db.Column("Campo", db.String(80))
    old_value = db.Column("DatosAntiguos", db.Text)
    new_value = db.Column("DatosNuevos", db.Text)
    result = db.Column("Accion", db.String(20), nullable=False, default="applied")  # applied/rejected/confirmed
    request_id = db.Column("IdSolicitud", db.String(40))
    username = db.Column("NombreUsuario", db.String(80))

    __table_args__ = (
        db.Index("ix_audit_log_section_created", "NombreTabla", "CreadoEn"),
    )
