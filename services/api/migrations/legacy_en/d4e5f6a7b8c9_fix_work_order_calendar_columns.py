"""fix missing work order calendar columns

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-02 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
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
    # ensure index for range queries exists
    indexes = [i['name'] for i in inspector.get_indexes('work_orders')]
    if 'ix_work_orders_assigned_scheduled' not in indexes:
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
