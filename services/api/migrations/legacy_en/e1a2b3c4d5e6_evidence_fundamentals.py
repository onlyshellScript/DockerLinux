"""evidence fundamentals

Revision ID: e1a2b3c4d5e6
Revises: c1d2e3f4a5b6
Create Date: 2026-11-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e1a2b3c4d5e6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


# Aplica esta revision de esquema de base de datos.
def upgrade():
    op.create_table(
        "visit_evidences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False, server_default="ADDITIONAL"),
        sa.Column("original_name", sa.String(length=250), nullable=True),
        sa.Column("storage_key", sa.String(length=120), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("declared_capture_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT"),
        sa.Column("previous_evidence_id", sa.Integer(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("duplicate_of_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=250), nullable=True),
        sa.Column("stored_name", sa.String(length=250), nullable=True),
        sa.Column("file_type", sa.String(length=50), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["previous_evidence_id"], ["visit_evidences.id"]),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["visit_evidences.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_visit_evidences_work_order_id", "visit_evidences", ["work_order_id"])
    op.create_index("ix_visit_evidences_storage_key", "visit_evidences", ["storage_key"], unique=True)
    op.create_index("ix_visit_evidences_sha256", "visit_evidences", ["sha256"], unique=False)

    op.create_table(
        "visit_signatures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=120), nullable=True),
        sa.Column("signer_name", sa.String(length=120), nullable=True),
        sa.Column("signer_role", sa.String(length=120), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acceptance_text", sa.Text(), nullable=True),
        sa.Column("consent_version", sa.String(length=40), nullable=True),
        sa.Column("technician_id", sa.Integer(), nullable=True),
        sa.Column("refused", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("refusal_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.ForeignKeyConstraint(["technician_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_visit_signatures_work_order_id", "visit_signatures", ["work_order_id"])

    op.create_table(
        "evidence_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["evidence_id"], ["visit_evidences.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_reviews_evidence_id", "evidence_reviews", ["evidence_id"])

    op.create_table(
        "evidence_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=True),
        sa.Column("evidence_id", sa.Integer(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.ForeignKeyConstraint(["evidence_id"], ["visit_evidences.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_events_work_order_id", "evidence_events", ["work_order_id"])
    op.create_index("ix_evidence_events_evidence_id", "evidence_events", ["evidence_id"])
    op.create_index("ix_evidence_events_created_at", "evidence_events", ["created_at"])

    op.create_table(
        "visit_checklist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=250), nullable=False),
        sa.Column("result", sa.String(length=30), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("checked_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.ForeignKeyConstraint(["checked_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_visit_checklist_items_work_order_id", "visit_checklist_items", ["work_order_id"])


# Aplica esta revision de esquema de base de datos.
def downgrade():
    op.drop_index("ix_visit_checklist_items_work_order_id", table_name="visit_checklist_items")
    op.drop_table("visit_checklist_items")

    op.drop_index("ix_evidence_events_created_at", table_name="evidence_events")
    op.drop_index("ix_evidence_events_evidence_id", table_name="evidence_events")
    op.drop_index("ix_evidence_events_work_order_id", table_name="evidence_events")
    op.drop_table("evidence_events")

    op.drop_index("ix_evidence_reviews_evidence_id", table_name="evidence_reviews")
    op.drop_table("evidence_reviews")

    op.drop_index("ix_visit_signatures_work_order_id", table_name="visit_signatures")
    op.drop_table("visit_signatures")

    op.drop_index("ix_visit_evidences_sha256", table_name="visit_evidences")
    op.drop_index("ix_visit_evidences_storage_key", table_name="visit_evidences")
    op.drop_index("ix_visit_evidences_work_order_id", table_name="visit_evidences")
    op.drop_table("visit_evidences")
