"""Add runtime identity, idempotency, and approval lifecycle fields.

Revision ID: f6a7b8c9d0e1
Revises: e5f0a1b2c3d4
Create Date: 2026-09-04 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agentrun",
        sa.Column("runtime_version", sa.String(length=80), nullable=False, server_default="aetherflow-runtime-v1"),
    )
    op.add_column("agentrun", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    op.add_column(
        "agentrun",
        sa.Column("approval_status", sa.String(length=30), nullable=False, server_default="not_required"),
    )
    op.add_column("agentrun", sa.Column("approval_comment", sa.String(length=500), nullable=True))
    op.add_column("agentrun", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agentrun", sa.Column("approved_by", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_agentrun_runtime_version"), "agentrun", ["runtime_version"], unique=False)
    op.create_index(op.f("ix_agentrun_idempotency_key"), "agentrun", ["idempotency_key"], unique=False)
    op.create_index(op.f("ix_agentrun_approval_status"), "agentrun", ["approval_status"], unique=False)
    op.execute(sa.text("UPDATE agentrun SET approval_status = 'pending' WHERE status = 'needs_human'"))


def downgrade():
    op.drop_index(op.f("ix_agentrun_approval_status"), table_name="agentrun")
    op.drop_index(op.f("ix_agentrun_idempotency_key"), table_name="agentrun")
    op.drop_index(op.f("ix_agentrun_runtime_version"), table_name="agentrun")
    op.drop_column("agentrun", "approved_by")
    op.drop_column("agentrun", "approved_at")
    op.drop_column("agentrun", "approval_comment")
    op.drop_column("agentrun", "approval_status")
    op.drop_column("agentrun", "idempotency_key")
    op.drop_column("agentrun", "runtime_version")
