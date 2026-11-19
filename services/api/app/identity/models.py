from datetime import datetime, timezone

import sqlalchemy as sa

from app.extensions import db

user_roles = db.Table(
    "UsuariosXRoles",
    db.Column("IdUsuario", db.Integer, db.ForeignKey("Usuarios.IdUsuario"), primary_key=True),
    db.Column("IdRol", db.Integer, db.ForeignKey("Roles.IdRol"), primary_key=True),
)


# User: modelo de base de datos que representa la entidad User.
class User(db.Model):
    __tablename__ = "Usuarios"

    id = db.Column("IdUsuario", db.Integer, primary_key=True)
    username = db.Column("Nombre_usuario", db.String(80), unique=True, nullable=False, index=True)
    email = db.Column("Correo", db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column("HashContrasena", db.String(256), nullable=False)
    is_active = db.Column("EstaActivo", db.Boolean, default=True, nullable=False)
    must_change_password = db.Column("DebeCambiarContrasena", db.Boolean, default=False, nullable=False, server_default=sa.text("0"))
    password_changed_at = db.Column("FechaCambioContrasena", db.DateTime(timezone=True))
    failed_attempts = db.Column("IntentosFallidos", db.Integer, default=0, nullable=False, server_default=sa.text("0"))
    locked_until = db.Column("BloqueadoHasta", db.DateTime(timezone=True))
    last_login = db.Column("UltimoAcceso", db.DateTime(timezone=True))
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column("ActualizadoEn", 
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    roles = db.relationship("Role", secondary=user_roles, backref="users", lazy="selectin")

# set_password: genera y almacena el hash de la contrasena en el usuario; entrada password; efecto secundario actualiza password_hash.
    def set_password(self, password):
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password)

# check_password: verifica si la contrasena coincide con el hash almacenado; entrada password; salida bool; sin efectos secundarios.
    def check_password(self, password):
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, password)

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "must_change_password": self.must_change_password,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "roles": [r.name for r in self.roles],
        }


# AuditEvent: modelo de base de datos que representa la entidad AuditEvent.
class AuditEvent(db.Model):
    __tablename__ = "AuditoriaEventos"

    id = db.Column("IdAuditoriaEvento", db.Integer, primary_key=True)
    actor_id = db.Column("IdActor", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    target_user_id = db.Column("IdUsuarioObjetivo", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    action = db.Column("Accion", db.String(40), nullable=False)
    changes = db.Column("Cambios", db.Text)
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "target_user_id": self.target_user_id,
            "action": self.action,
            "changes": self.changes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Role: modelo de base de datos que representa la entidad Role.
class Role(db.Model):
    __tablename__ = "Roles"

    id = db.Column("IdRol", db.Integer, primary_key=True)
    name = db.Column("Nombre", db.String(50), unique=True, nullable=False, index=True)
    description = db.Column("Descripcion", db.String(200))

# to_dict: serializa el rol a diccionario con id, nombre y descripcion; sin parametros; sin efectos secundarios.
    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description}


# UserSession: sesion de acceso emitida en cada login. Los tokens (access y refresh) llevan su id en el claim "sid";
# al cerrar sesion se marca RevocadaEn y ningun token de esa sesion vuelve a ser aceptado, aunque no haya expirado.
class UserSession(db.Model):
    __tablename__ = "SesionesUsuario"

    id = db.Column("IdSesion", db.String(36), primary_key=True)
    user_id = db.Column("IdUsuario", db.Integer, db.ForeignKey("Usuarios.IdUsuario"), nullable=False, index=True)
    created_at = db.Column("CreadaEn", db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column("ExpiraEn", db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column("RevocadaEn", db.DateTime(timezone=True))
    revoked_reason = db.Column("MotivoRevocacion", db.String(40))
    ip_address = db.Column("IpOrigen", db.String(45))

# is_active: la sesion no fue revocada ni supero su vencimiento (el del refresh token).
    def is_active(self, now=None):
        if self.revoked_at is not None:
            return False
        now = now or datetime.now(timezone.utc)
        exp = self.expires_at
        if exp is not None and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp is None or exp > now
