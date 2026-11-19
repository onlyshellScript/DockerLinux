"""reclamacion atomica de notificaciones

- Notificaciones.ReclamadoEn (nullable): momento en que un procesador reclamo la notificacion (Estado='processing').
  Permite que dos procesadores (SIGOS-Worker y POST /notifications/process, o dos workers) no envien la misma
  notificacion y que una reclamacion abandonada por un proceso caido vuelva a 'pending'.

Solo agrega una columna nullable: compatible con los datos actuales (quedan en NULL). Idempotente.
El downgrade elimina la columna (sin perdida de datos de negocio: solo es un marcador de procesamiento).

Revision ID: b8d9e0f1a2c3
Revises: a7c8e9f0b1d2
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa


revision = 'b8d9e0f1a2c3'
down_revision = 'a7c8e9f0b1d2'
branch_labels = None
depends_on = None


def _columns():
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns('Notificaciones')}


def upgrade():
    if 'ReclamadoEn' not in _columns():
        with op.batch_alter_table('Notificaciones', schema=None) as batch_op:
            batch_op.add_column(sa.Column('ReclamadoEn', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    if 'ReclamadoEn' in _columns():
        with op.batch_alter_table('Notificaciones', schema=None) as batch_op:
            batch_op.drop_column('ReclamadoEn')
