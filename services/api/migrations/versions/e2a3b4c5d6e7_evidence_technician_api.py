"""evidence technician api

Revision ID: e2a3b4c5d6e7
Revises: e1a2b3c4d5e6
Create Date: 2026-11-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e2a3b4c5d6e7"
down_revision = "e1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("visit_evidences", schema=None) as batch_op:
        batch_op.add_column(sa.Column("client_operation_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_visit_evidences_client_operation_id", ["client_operation_id"], unique=False)
    with op.batch_alter_table("visit_signatures", schema=None) as batch_op:
        batch_op.add_column(sa.Column("client_operation_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_visit_signatures_client_operation_id", ["client_operation_id"], unique=False)


def downgrade():
    with op.batch_alter_table("visit_signatures", schema=None) as batch_op:
        batch_op.drop_index("ix_visit_signatures_client_operation_id")
        batch_op.drop_column("client_operation_id")
    with op.batch_alter_table("visit_evidences", schema=None) as batch_op:
        batch_op.drop_index("ix_visit_evidences_client_operation_id")
        batch_op.drop_column("client_operation_id")
