"""Persist Agent Reliability experiments

Revision ID: e5f0a1b2c3d4
Revises: c7a91f3a9b2d
Create Date: 2026-07-11 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e5f0a1b2c3d4"
down_revision = "c7a91f3a9b2d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agentexperiment",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_name", sa.String(length=160), nullable=False),
        sa.Column("dataset_key", sa.String(length=40), nullable=False),
        sa.Column("runtime_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("release_gate_status", sa.String(length=20), nullable=False),
        sa.Column("release_gate_label", sa.String(length=30), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agentexperiment_dataset_key"), "agentexperiment", ["dataset_key"], unique=False)
    op.create_index(op.f("ix_agentexperiment_owner_id"), "agentexperiment", ["owner_id"], unique=False)
    op.create_index(op.f("ix_agentexperiment_release_gate_status"), "agentexperiment", ["release_gate_status"], unique=False)
    op.create_index(op.f("ix_agentexperiment_status"), "agentexperiment", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_agentexperiment_status"), table_name="agentexperiment")
    op.drop_index(op.f("ix_agentexperiment_release_gate_status"), table_name="agentexperiment")
    op.drop_index(op.f("ix_agentexperiment_owner_id"), table_name="agentexperiment")
    op.drop_index(op.f("ix_agentexperiment_dataset_key"), table_name="agentexperiment")
    op.drop_table("agentexperiment")
