"""calendar scheduling fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-29 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


# Aplica esta revision de esquema de base de datos.
def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('work_orders')]
    if 'scheduled_end' not in cols:
        op.add_column('work_orders', sa.Column('scheduled_end', sa.DateTime(timezone=True), nullable=True))
    if 'schedule_notes' not in cols:
        op.add_column('work_orders', sa.Column('schedule_notes', sa.Text(), nullable=True))
    if 'version' not in cols:
        op.add_column('work_orders', sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text("0")))
    # index for range queries (ix_work_orders_scheduled_at already exists from a081)
    try:
        op.create_index('ix_work_orders_assigned_scheduled', 'work_orders', ['assigned_to_id', 'scheduled_at'])
    except Exception:
        pass


# Aplica esta revision de esquema de base de datos.
def downgrade():
    try:
        op.drop_index('ix_work_orders_assigned_scheduled', table_name='work_orders')
    except Exception:
        pass
    try:
        op.drop_column('work_orders', 'version')
    except Exception:
        pass
    try:
        op.drop_column('work_orders', 'schedule_notes')
    except Exception:
        pass
    try:
        op.drop_column('work_orders', 'scheduled_end')
    except Exception:
        pass
