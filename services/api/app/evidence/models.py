# -*- coding: utf-8 -*-
from datetime import datetime, timezone

import sqlalchemy as sa

from app.extensions import db

# Validation states (independent from work order operational status)
EVIDENCE_DRAFT = "DRAFT"
EVIDENCE_SUBMITTED = "SUBMITTED"
EVIDENCE_UNDER_REVIEW = "UNDER_REVIEW"
EVIDENCE_CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
EVIDENCE_RESUBMITTED = "RESUBMITTED"
EVIDENCE_APPROVED = "APPROVED"
EVIDENCE_REJECTED = "REJECTED"

EVIDENCE_STATES = [
    EVIDENCE_DRAFT,
    EVIDENCE_SUBMITTED,
    EVIDENCE_UNDER_REVIEW,
    EVIDENCE_CORRECTION_REQUIRED,
    EVIDENCE_RESUBMITTED,
    EVIDENCE_APPROVED,
    EVIDENCE_REJECTED,
]

EVIDENCE_TRANSITIONS = {
    EVIDENCE_DRAFT: {EVIDENCE_SUBMITTED},
    EVIDENCE_SUBMITTED: {EVIDENCE_UNDER_REVIEW},
    EVIDENCE_UNDER_REVIEW: {EVIDENCE_CORRECTION_REQUIRED, EVIDENCE_APPROVED, EVIDENCE_REJECTED},
    EVIDENCE_CORRECTION_REQUIRED: {EVIDENCE_RESUBMITTED},
    EVIDENCE_RESUBMITTED: {EVIDENCE_UNDER_REVIEW},
    EVIDENCE_APPROVED: set(),
    EVIDENCE_REJECTED: set(),
}

# Categories
CATEGORY_BEFORE = "BEFORE"
CATEGORY_DURING = "DURING"
CATEGORY_AFTER = "AFTER"
CATEGORY_ADDITIONAL = "ADDITIONAL"

EVIDENCE_CATEGORIES = [CATEGORY_BEFORE, CATEGORY_DURING, CATEGORY_AFTER, CATEGORY_ADDITIONAL]


class VisitEvidence(db.Model):
    __tablename__ = "visit_evidences"

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"), nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False, default=CATEGORY_ADDITIONAL, server_default=CATEGORY_ADDITIONAL)
    original_name = db.Column(db.String(250))
    storage_key = db.Column(db.String(120), unique=True, index=True)
    mime_type = db.Column(db.String(100))
    size_bytes = db.Column(db.Integer)
    sha256 = db.Column(db.String(64), index=True)
    declared_capture_at = db.Column(db.DateTime(timezone=True))
    received_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(30), nullable=False, default=EVIDENCE_DRAFT, server_default=EVIDENCE_DRAFT)
    previous_evidence_id = db.Column(db.Integer, db.ForeignKey("visit_evidences.id"))
    version_number = db.Column(db.Integer, nullable=False, default=1, server_default=sa.text("1"))
    duplicate_of_id = db.Column(db.Integer, db.ForeignKey("visit_evidences.id"))

    # Compatibility columns retained for existing records/APIs
    file_name = db.Column(db.String(250))
    stored_name = db.Column(db.String(250))
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    work_order = db.relationship("WorkOrder")
    uploaded_by = db.relationship("User")
    previous_evidence = db.relationship("VisitEvidence", remote_side=[id], foreign_keys=[previous_evidence_id])
    duplicate_of = db.relationship("VisitEvidence", remote_side=[id], foreign_keys=[duplicate_of_id])
    reviews = db.relationship("EvidenceReview", backref="evidence", cascade="all, delete-orphan", order_by="EvidenceReview.created_at")

    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "category": self.category,
            "original_name": self.original_name or self.file_name,
            "storage_key": self.storage_key or self.stored_name,
            "mime_type": self.mime_type or self.file_type,
            "size_bytes": self.size_bytes if self.size_bytes is not None else self.file_size,
            "sha256": self.sha256,
            "declared_capture_at": self.declared_capture_at.isoformat() if self.declared_capture_at else None,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "uploaded_by": self.uploaded_by.to_dict() if self.uploaded_by else None,
            "uploaded_by_id": self.uploaded_by_id,
            "description": self.description,
            "status": self.status,
            "previous_evidence_id": self.previous_evidence_id,
            "version_number": self.version_number,
            "duplicate_of_id": self.duplicate_of_id,
            "file_name": self.file_name or self.original_name,
            "stored_name": self.stored_name or self.storage_key,
            "file_type": self.file_type or self.mime_type,
            "file_size": self.file_size if self.file_size is not None else self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class VisitSignature(db.Model):
    __tablename__ = "visit_signatures"

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"), nullable=False, index=True)
    storage_key = db.Column(db.String(120))
    signer_name = db.Column(db.String(120))
    signer_role = db.Column(db.String(120))
    received_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    acceptance_text = db.Column(db.Text)
    consent_version = db.Column(db.String(40))
    technician_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    refused = db.Column(db.Boolean, nullable=False, default=False, server_default=sa.text("0"))
    refusal_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    work_order = db.relationship("WorkOrder")
    technician = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "storage_key": self.storage_key,
            "signer_name": self.signer_name,
            "signer_role": self.signer_role,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "acceptance_text": self.acceptance_text,
            "consent_version": self.consent_version,
            "technician_id": self.technician_id,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EvidenceReview(db.Model):
    __tablename__ = "evidence_reviews"

    id = db.Column(db.Integer, primary_key=True)
    evidence_id = db.Column(db.Integer, db.ForeignKey("visit_evidences.id"), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    decision = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reviewer = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "evidence_id": self.evidence_id,
            "reviewer_id": self.reviewer_id,
            "decision": self.decision,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EvidenceEvent(db.Model):
    __tablename__ = "evidence_events"

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"), index=True)
    evidence_id = db.Column(db.Integer, db.ForeignKey("visit_evidences.id"), index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(40), nullable=False)
    from_status = db.Column(db.String(30))
    to_status = db.Column(db.String(30))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    actor = db.relationship("User")
    evidence = db.relationship("VisitEvidence")

    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "evidence_id": self.evidence_id,
            "actor_id": self.actor_id,
            "action": self.action,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class VisitChecklistItem(db.Model):
    __tablename__ = "visit_checklist_items"

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"), nullable=False, index=True)
    label = db.Column(db.String(250), nullable=False)
    result = db.Column(db.String(30))
    notes = db.Column(db.Text)
    checked_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    checked_by = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "label": self.label,
            "result": self.result,
            "notes": self.notes,
            "checked_by_id": self.checked_by_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Backwards-compatible alias
Evidence = VisitEvidence
ALL_TYPES = ["photo", "document", "observation"]
