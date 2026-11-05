"""materials ledger: code, decimal price, stock threshold, initial balances

Revision ID: f4a5b6c7d8e9
Revises: e6f7a8b9c0d1
Create Date: 2026-11-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f4a5b6c7d8e9'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('materials', sa.Column('code', sa.String(40), nullable=True))
    op.create_index('ix_materials_code', 'materials', ['code'], unique=True)
    op.alter_column('materials', 'unit_price',
                    type_=sa.Numeric(18, 2),
                    existing_type=sa.Float())
    op.add_column('operational_settings',
                  sa.Column('stock_critical_threshold', sa.Float(), nullable=False, server_default=sa.text('0.5')))

    # backfill code
    op.execute("UPDATE materials SET code = 'MAT-' + CAST(id AS VARCHAR(20)) WHERE code IS NULL")

    # initial balance movement
    op.execute("""
        INSERT INTO stock_movements (material_id, quantity, movement_type, user_id, notes, created_at)
        SELECT m.id, m.current_stock, 'ADJUSTMENT', 1, 'Saldo inicial', GETUTCDATE()
        FROM materials m
        WHERE m.current_stock > 0
          AND NOT EXISTS (SELECT 1 FROM stock_movements sm WHERE sm.material_id = m.id)
    """)


def downgrade():
    op.execute("DELETE FROM stock_movements WHERE movement_type = 'ADJUSTMENT' AND notes = 'Saldo inicial'")
    op.drop_column('operational_settings', 'stock_critical_threshold')
    op.alter_column('materials', 'unit_price',
                    type_=sa.Float(),
                    existing_type=sa.Numeric(18, 2))
    op.drop_index('ix_materials_code', table_name='materials')
    op.drop_column('materials', 'code')
