"""settings tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-29 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


# Aplica esta revision de esquema de base de datos.
def upgrade():
    op.create_table(
        'organization_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_name', sa.String(length=150), nullable=False, server_default='SIGOS'),
        sa.Column('nit', sa.String(length=40), nullable=True),
        sa.Column('admin_email', sa.String(length=120), nullable=False, server_default='admin@sigos.local'),
        sa.Column('contact_phone', sa.String(length=30), nullable=True),
        sa.Column('address', sa.String(length=250), nullable=True),
        sa.Column('city_id', sa.Integer(), sa.ForeignKey('cities.id', ondelete='NO ACTION'), nullable=True),
        sa.Column('timezone', sa.String(length=60), nullable=False, server_default='America/Bogota'),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'operational_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('work_days', sa.String(length=20), nullable=False, server_default='1,2,3,4,5'),
        sa.Column('work_start', sa.String(length=5), nullable=False, server_default='07:00'),
        sa.Column('work_end', sa.String(length=5), nullable=False, server_default='18:00'),
        sa.Column('default_visit_duration', sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column('max_visit_duration', sa.Integer(), nullable=False, server_default=sa.text("480")),
        sa.Column('min_advance_hours', sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column('travel_margin_minutes', sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column('calendar_interval', sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'security_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_inactivity_minutes', sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column('session_max_hours', sa.Integer(), nullable=False, server_default=sa.text("8")),
        sa.Column('password_min_length', sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column('password_history_count', sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column('lock_attempts', sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column('lock_minutes', sa.Integer(), nullable=False, server_default=sa.text("15")),
        sa.Column('temp_password_validity_days', sa.Integer(), nullable=False, server_default=sa.text("7")),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'notification_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('preferences', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'user_notification_preferences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='NO ACTION'), nullable=False, unique=True),
        sa.Column('preferences', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('section', sa.String(length=40), nullable=False, index=True),
        sa.Column('field', sa.String(length=80), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('result', sa.String(length=20), nullable=False, server_default='applied'),
        sa.Column('request_id', sa.String(length=40), nullable=True),
        sa.Column('username', sa.String(length=80), nullable=True),
    )
    # seed one row each
    op.execute("INSERT INTO organization_settings (company_name, admin_email, timezone) VALUES ('SIGOS','admin@sigos.local','America/Bogota')")
    op.execute("SET IDENTITY_INSERT operational_settings ON; INSERT INTO operational_settings (id) VALUES (1); SET IDENTITY_INSERT operational_settings OFF;")
    op.execute("SET IDENTITY_INSERT security_settings ON; INSERT INTO security_settings (id) VALUES (1); SET IDENTITY_INSERT security_settings OFF;")
    op.execute("INSERT INTO notification_settings (preferences) VALUES ('{}')")


# Aplica esta revision de esquema de base de datos.
def downgrade():
    op.drop_table('audit_log')
    op.drop_table('user_notification_preferences')
    op.drop_table('notification_settings')
    op.drop_table('security_settings')
    op.drop_table('operational_settings')
    op.drop_table('organization_settings')
