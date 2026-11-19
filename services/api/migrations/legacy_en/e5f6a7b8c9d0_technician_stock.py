"""technician stock table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


# Aplica esta revision de esquema de base de datos.
def upgrade():
    op.create_table(
        'technician_stock',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('technician_id', sa.Integer(), sa.ForeignKey('technician_profiles.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('material_id', sa.Integer(), sa.ForeignKey('materials.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('quantity', sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('technician_id', 'material_id', name='uq_tech_material'),
    )


# Aplica esta revision de esquema de base de datos.
def downgrade():
    op.drop_table('technician_stock')
