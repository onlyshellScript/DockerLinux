"""material requests tables

Revision ID: e6f7a8b9c0d1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e6f7a8b9c0d1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'material_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('requester_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='NO ACTION'), nullable=False, index=True),
        sa.Column('technician_id', sa.Integer(), sa.ForeignKey('technician_profiles.id', ondelete='NO ACTION'), nullable=True, index=True),
        sa.Column('work_order_id', sa.Integer(), sa.ForeignKey('work_orders.id', ondelete='NO ACTION'), nullable=True, index=True),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'pendiente'")),
        sa.Column('reason', sa.Text()),
        sa.Column('approved_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='NO ACTION'), nullable=True),
        sa.Column('approval_reason', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'material_request_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('material_requests.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('material_id', sa.Integer(), sa.ForeignKey('materials.id', ondelete='NO ACTION'), nullable=False, index=True),
        sa.Column('quantity', sa.Float(), nullable=False),
    )


def downgrade():
    op.drop_table('material_request_items')
    op.drop_table('material_requests')
