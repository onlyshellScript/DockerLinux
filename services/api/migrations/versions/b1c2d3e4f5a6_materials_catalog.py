"""materials catalog: categories, units, catalog items, catalog_item_id

Revision ID: b1c2d3e4f5a6
Revises: f4a5b6c7d8e9
Create Date: 2026-11-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b1c2d3e4f5a6'
down_revision = 'f4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'material_categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(40), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('name_norm', sa.String(120), nullable=False, unique=True, index=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
    )
    op.create_table(
        'material_units',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(20), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(60), nullable=False),
        sa.Column('name_norm', sa.String(60), nullable=False, unique=True, index=True),
        sa.Column('allows_decimal', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
    )
    op.create_table(
        'material_catalog',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('material_categories.id', ondelete='NO ACTION'), nullable=False, index=True),
        sa.Column('code', sa.String(40), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('name_norm', sa.String(200), nullable=False, unique=True, index=True),
        sa.Column('unit_id', sa.Integer(), sa.ForeignKey('material_units.id', ondelete='NO ACTION'), nullable=False, index=True),
        sa.Column('measure', sa.String(60)),
        sa.Column('stage', sa.String(60)),
        sa.Column('applies_to', sa.String(40)),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
    )
    op.add_column('materials', sa.Column('catalog_item_id', sa.Integer(), sa.ForeignKey('material_catalog.id', ondelete='NO ACTION'), nullable=True, unique=True, index=True))


def downgrade():
    op.drop_column('materials', 'catalog_item_id')
    op.drop_table('material_catalog')
    op.drop_table('material_units')
    op.drop_table('material_categories')
