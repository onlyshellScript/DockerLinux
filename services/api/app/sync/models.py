from datetime import datetime, timezone

from app.extensions import db

SYNC_PENDING = "pending"
SYNC_SYNCED = "synced"
SYNC_FAILED = "failed"

ALL_STATUSES = [SYNC_PENDING, SYNC_SYNCED, SYNC_FAILED]


class SyncOperation(db.Model):
    __tablename__ = "sync_operations"

    id = db.Column(db.Integer, primary_key=True)
    client_operation_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    operation_type = db.Column(db.String(50), nullable=False)
    payload = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(15), nullable=False, default=SYNC_PENDING, index=True)
    result = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    synced_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "client_operation_id": self.client_operation_id,
            "operation_type": self.operation_type,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
        }
