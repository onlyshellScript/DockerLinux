"""sesiones revocables y firma del tecnico en evidencias

- SesionesUsuario: una fila por login; los JWT llevan su id (claim sid) y el logout la revoca.
- FirmasTecnico: versiones inmutables de la firma de perfil de cada tecnico.
- Evidencias: columnas nullable de la firma historica (los registros existentes quedan en NULL, sin cambios).

Solo agrega tablas y columnas nullable: compatible con los datos actuales. Se encadena a la cabeza valida de la
cadena en espanol (615483f3bc21). Es idempotente: omite lo que ya exista (por ejemplo, si se aplico el script SQL
manual docs/database/2026-11-18_sesiones_firmas.sql).

Revision ID: a7c8e9f0b1d2
Revises: 615483f3bc21
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa


revision = 'a7c8e9f0b1d2'
down_revision = '615483f3bc21'
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade():
    insp = _inspector()
    tables = set(insp.get_table_names())

    if 'SesionesUsuario' not in tables:
        op.create_table(
            'SesionesUsuario',
            sa.Column('IdSesion', sa.String(36), primary_key=True),
            sa.Column('IdUsuario', sa.Integer, sa.ForeignKey('Usuarios.IdUsuario', name='FK_SesionesUsuario_Usuarios'), nullable=False),
            sa.Column('CreadaEn', sa.DateTime(timezone=True), nullable=False),
            sa.Column('ExpiraEn', sa.DateTime(timezone=True), nullable=False),
            sa.Column('RevocadaEn', sa.DateTime(timezone=True), nullable=True),
            sa.Column('MotivoRevocacion', sa.String(40), nullable=True),
            sa.Column('IpOrigen', sa.String(45), nullable=True),
        )
        op.create_index('IX_SesionesUsuario_IdUsuario', 'SesionesUsuario', ['IdUsuario'])

    if 'FirmasTecnico' not in tables:
        op.create_table(
            'FirmasTecnico',
            sa.Column('IdFirmaTecnico', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('IdUsuario', sa.Integer, sa.ForeignKey('Usuarios.IdUsuario', name='FK_FirmasTecnico_Usuarios'), nullable=False),
            sa.Column('ClaveAlmacenamiento', sa.String(120), nullable=False),
            sa.Column('TipoArchivo', sa.String(100), nullable=False),
            sa.Column('TamanoArchivo', sa.Integer, nullable=False),
            sa.Column('Sha256', sa.String(64), nullable=False),
            sa.Column('Version', sa.Integer, nullable=False, server_default=sa.text('1')),
            sa.Column('EsActiva', sa.Boolean, nullable=False, server_default=sa.text('1')),
            sa.Column('CreadaEn', sa.DateTime(timezone=True), nullable=False),
            sa.Column('ReemplazadaEn', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('ClaveAlmacenamiento', name='UQ_FirmasTecnico_ClaveAlmacenamiento'),
        )
        op.create_index('IX_FirmasTecnico_IdUsuario', 'FirmasTecnico', ['IdUsuario'])

    cols = {c['name'] for c in _inspector().get_columns('Evidencias')}
    with op.batch_alter_table('Evidencias') as batch:
        if 'IdFirmaTecnico' not in cols:
            batch.add_column(sa.Column('IdFirmaTecnico', sa.Integer, nullable=True))
            batch.create_foreign_key('FK_Evidencias_FirmasTecnico', 'FirmasTecnico', ['IdFirmaTecnico'], ['IdFirmaTecnico'])
        if 'FirmaTecnicoSha256' not in cols:
            batch.add_column(sa.Column('FirmaTecnicoSha256', sa.String(64), nullable=True))
        if 'IdTecnicoFirmante' not in cols:
            batch.add_column(sa.Column('IdTecnicoFirmante', sa.Integer, nullable=True))
            batch.create_foreign_key('FK_Evidencias_TecnicoFirmante', 'Usuarios', ['IdTecnicoFirmante'], ['IdUsuario'])
        if 'FechaFirmaTecnico' not in cols:
            batch.add_column(sa.Column('FechaFirmaTecnico', sa.DateTime(timezone=True), nullable=True))
    idx = {i['name'] for i in _inspector().get_indexes('Evidencias')}
    if 'IX_Evidencias_IdFirmaTecnico' not in idx:
        op.create_index('IX_Evidencias_IdFirmaTecnico', 'Evidencias', ['IdFirmaTecnico'])


def downgrade():
    # Quitar estas tablas borraria la firma historica de evidencias ya registradas. Se revierte solo si ninguna
    # evidencia tiene firma; en otro caso se aborta para no perder registros.
    bind = op.get_bind()
    signed = bind.execute(sa.text('SELECT COUNT(*) FROM Evidencias WHERE IdFirmaTecnico IS NOT NULL')).scalar()
    if signed:
        raise RuntimeError('Hay evidencias con firma del tecnico; no se revierte para conservar la firma historica')
    op.drop_index('IX_Evidencias_IdFirmaTecnico', table_name='Evidencias')
    with op.batch_alter_table('Evidencias') as batch:
        batch.drop_constraint('FK_Evidencias_TecnicoFirmante', type_='foreignkey')
        batch.drop_constraint('FK_Evidencias_FirmasTecnico', type_='foreignkey')
        batch.drop_column('FechaFirmaTecnico')
        batch.drop_column('IdTecnicoFirmante')
        batch.drop_column('FirmaTecnicoSha256')
        batch.drop_column('IdFirmaTecnico')
    op.drop_index('IX_FirmasTecnico_IdUsuario', table_name='FirmasTecnico')
    op.drop_table('FirmasTecnico')
    op.drop_index('IX_SesionesUsuario_IdUsuario', table_name='SesionesUsuario')
    op.drop_table('SesionesUsuario')
