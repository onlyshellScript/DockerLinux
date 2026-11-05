from datetime import datetime, timezone

from app.extensions import db

EVIDENCE_PHOTO = "photo"
EVIDENCE_DOCUMENT = "document"
EVIDENCE_OBSERVATION = "observation"

ALL_TYPES = [EVIDENCE_PHOTO, EVIDENCE_DOCUMENT, EVIDENCE_OBSERVATION]


class Evidence(db.Model):
    __tablename__ = "evidences"

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"), nullable=False, index=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    evidence_type = db.Column(db.String(20), nullable=False)
    file_name = db.Column(db.String(250))
    stored_name = db.Column(db.String(250))
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    work_order = db.relationship("WorkOrder")
    uploaded_by = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "uploaded_by": self.uploaded_by.to_dict() if self.uploaded_by else None,
            "evidence_type": self.evidence_type,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
