"""evolve material requests: partials, deliveries, events, idempotency

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-11-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d2e3f4a5b6'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


# Aplica esta revision de esquema de base de datos.
def upgrade():
# Aplica esta revision de esquema de base de datos.
    op.alter_column('material_requests', 'status', type_=sa.String(30), existing_type=sa.String(20), existing_nullable=False)
    op.add_column('material_requests', sa.Column('client_operation_id', sa.String(36), nullable=True))
    op.create_index('ix_material_requests_client_operation_id', 'material_requests', ['client_operation_id'], unique=True)
    op.add_column('material_requests', sa.Column('delivered_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='NO ACTION'), nullable=True))

    op.execute("UPDATE material_requests SET status='SUBMITTED' WHERE status='pendiente'")
    op.execute("UPDATE material_requests SET status='APPROVED' WHERE status='autorizada'")
    op.execute("UPDATE material_requests SET status='REJECTED' WHERE status='rechazada'")
    op.execute("UPDATE material_requests SET status='DELIVERED' WHERE status='entregada'")

    op.add_column('material_request_items', sa.Column('quantity_requested', sa.Float(), nullable=True))
    op.add_column('material_request_items', sa.Column('quantity_approved', sa.Float(), nullable=False, server_default=sa.text('0')))
    op.add_column('material_request_items', sa.Column('quantity_delivered', sa.Float(), nullable=False, server_default=sa.text('0')))
    op.execute("UPDATE material_request_items SET quantity_requested = quantity WHERE quantity_requested IS NULL")
    op.alter_column('material_request_items', 'quantity_requested', type_=sa.Float(), existing_type=sa.Float(), nullable=False)

    op.create_table(
        'material_request_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('material_requests.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='NO ACTION'), nullable=True),
        sa.Column('action', sa.String(40), nullable=False),
        sa.Column('from_status', sa.String(30)),
        sa.Column('to_status', sa.String(30)),
        sa.Column('payload', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.create_table(
        'material_request_deliveries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('material_requests.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='NO ACTION'), nullable=False),
        sa.Column('operation_id', sa.String(36), index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.create_table(
        'material_request_delivery_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('delivery_id', sa.Integer(), sa.ForeignKey('material_request_deliveries.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('request_item_id', sa.Integer(), sa.ForeignKey('material_request_items.id', ondelete='NO ACTION'), nullable=False, index=True),
        sa.Column('quantity_delivered', sa.Float(), nullable=False),
        sa.Column('movement_id', sa.Integer(), sa.ForeignKey('stock_movements.id', ondelete='NO ACTION')),
    )
    op.create_table(
        'material_request_operations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('operation_id', sa.String(36), nullable=False, unique=True, index=True),
        sa.Column('operation_type', sa.String(40), nullable=False, index=True),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='NO ACTION'), nullable=True),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('material_requests.id', ondelete='NO ACTION'), nullable=True, index=True),
        sa.Column('result', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )


# Aplica esta revision de esquema de base de datos.
def downgrade():
    op.drop_table('material_request_operations')
    op.drop_table('material_request_delivery_items')
    op.drop_table('material_request_deliveries')
    op.drop_table('material_request_events')
    for col in ('quantity_delivered', 'quantity_approved', 'quantity_requested'):
        op.execute(f"""
        IF EXISTS (SELECT 1 FROM sys.default_constraints
                   WHERE parent_object_id = OBJECT_ID('material_request_items')
                     AND col_name(parent_object_id, parent_column_id) = '{col}')
        BEGIN
            DECLARE @c_{col} VARCHAR(256);
            SELECT @c_{col} = name FROM sys.default_constraints
            WHERE parent_object_id = OBJECT_ID('material_request_items')
              AND col_name(parent_object_id, parent_column_id) = '{col}';
            EXEC('ALTER TABLE material_request_items DROP CONSTRAINT ' + @c_{col});
        END
        """)
        op.drop_column('material_request_items', col)
    op.execute("""
    DECLARE @fk VARCHAR(256);
    SELECT @fk = name FROM sys.foreign_keys
    WHERE parent_object_id = OBJECT_ID('material_requests')
      AND name LIKE '%deliv%';
    IF @fk IS NOT NULL
        EXEC('ALTER TABLE material_requests DROP CONSTRAINT ' + @fk);
    """)
    op.drop_column('material_requests', 'delivered_by_id')
    op.drop_index('ix_material_requests_client_operation_id', table_name='material_requests')
    op.drop_column('material_requests', 'client_operation_id')
    op.alter_column('material_requests', 'status', type_=sa.String(20), existing_type=sa.String(30), existing_nullable=False)
