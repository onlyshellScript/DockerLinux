from datetime import datetime, timezone

from app.extensions import db

CHANNEL_EMAIL = "email"
CHANNEL_WHATSAPP = "whatsapp"
ALL_CHANNELS = [CHANNEL_EMAIL, CHANNEL_WHATSAPP]

STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
ALL_STATUSES = [STATUS_PENDING, STATUS_SENT, STATUS_FAILED]

MAX_RETRIES = 3


# Notification: modelo de base de datos que representa la entidad Notification.
class Notification(db.Model):
    __tablename__ = "Notificaciones"

    id = db.Column("IdNotificacion", db.Integer, primary_key=True)
    user_id = db.Column("IdUsuario", db.Integer, db.ForeignKey("Usuarios.IdUsuario"), nullable=False, index=True)
    channel = db.Column("Canal", db.String(15), nullable=False)
    recipient = db.Column("Destinatario", db.String(250), nullable=False)
    subject = db.Column("Asunto", db.String(200))
    message = db.Column("Mensaje", db.Text, nullable=False)
    status = db.Column("Estado", db.String(15), nullable=False, default=STATUS_PENDING, index=True)
    retry_count = db.Column("Intentos", db.Integer, nullable=False, default=0)
    error_message = db.Column("MensajeError", db.String(500))
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sent_at = db.Column("EnviadoEn", db.DateTime(timezone=True))

    user = db.relationship("User")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "channel": self.channel,
            "recipient": self.recipient,
            "subject": self.subject,
            "message": self.message,
            "status": self.status,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }
