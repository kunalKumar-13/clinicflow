"""create appointments table

Revision ID: 0001
Revises:
Create Date: 2026-10-07

The first and only migration: it creates the appointments table together with the
indexes the list and stats queries rely on (doctor, scheduled_at, status).
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("patient_name", sa.String(length=120), nullable=False),
        sa.Column("patient_phone", sa.String(length=20), nullable=False),
        sa.Column("doctor", sa.String(length=120), nullable=False),
        sa.Column("department", sa.String(length=60), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="scheduled"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_appointments_id", "appointments", ["id"])
    op.create_index("ix_appointments_doctor", "appointments", ["doctor"])
    op.create_index("ix_appointments_scheduled_at", "appointments", ["scheduled_at"])
    op.create_index("ix_appointments_status", "appointments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_appointments_status", table_name="appointments")
    op.drop_index("ix_appointments_scheduled_at", table_name="appointments")
    op.drop_index("ix_appointments_doctor", table_name="appointments")
    op.drop_index("ix_appointments_id", table_name="appointments")
    op.drop_table("appointments")
