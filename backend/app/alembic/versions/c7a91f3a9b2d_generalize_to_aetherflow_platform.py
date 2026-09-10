"""Generalize legacy demo into AetherFlow workflow platform

Revision ID: c7a91f3a9b2d
Revises: b83f2a6d41c2
Create Date: 2026-06-23 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "c7a91f3a9b2d"
down_revision = "b83f2a6d41c2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workflowtask",
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("objective", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("context", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("expected_output", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("scenario_hint", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column("priority", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("risk_level", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("owner_team", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column("final_summary", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflowtask_priority"), "workflowtask", ["priority"], unique=False)
    op.create_index(op.f("ix_workflowtask_requires_approval"), "workflowtask", ["requires_approval"], unique=False)
    op.create_index(op.f("ix_workflowtask_risk_level"), "workflowtask", ["risk_level"], unique=False)
    op.create_index(op.f("ix_workflowtask_scenario_hint"), "workflowtask", ["scenario_hint"], unique=False)
    op.create_index(op.f("ix_workflowtask_status"), "workflowtask", ["status"], unique=False)

    op.add_column("agentrun", sa.Column("task_id", sa.Uuid(), nullable=True))
    op.add_column(
        "agentrun",
        sa.Column(
            "risk_level",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
            server_default="medium",
        ),
    )
    op.add_column(
        "agentrun",
        sa.Column("graph_node_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "agentrun",
        sa.Column("cost_units", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_agentrun_task_id_workflowtask",
        "agentrun",
        "workflowtask",
        ["task_id"],
        ["id"],
    )
    op.create_index(op.f("ix_agentrun_task_id"), "agentrun", ["task_id"], unique=False)
    op.create_index(op.f("ix_agentrun_risk_level"), "agentrun", ["risk_level"], unique=False)
    op.alter_column("agentrun", "ticket_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column("agentrun", "risk_level", server_default=None)
    op.alter_column("agentrun", "graph_node_count", server_default=None)
    op.alter_column("agentrun", "cost_units", server_default=None)


def downgrade():
    op.alter_column("agentrun", "ticket_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_index(op.f("ix_agentrun_risk_level"), table_name="agentrun")
    op.drop_index(op.f("ix_agentrun_task_id"), table_name="agentrun")
    op.drop_constraint("fk_agentrun_task_id_workflowtask", "agentrun", type_="foreignkey")
    op.drop_column("agentrun", "cost_units")
    op.drop_column("agentrun", "graph_node_count")
    op.drop_column("agentrun", "risk_level")
    op.drop_column("agentrun", "task_id")

    op.drop_index(op.f("ix_workflowtask_status"), table_name="workflowtask")
    op.drop_index(op.f("ix_workflowtask_scenario_hint"), table_name="workflowtask")
    op.drop_index(op.f("ix_workflowtask_risk_level"), table_name="workflowtask")
    op.drop_index(op.f("ix_workflowtask_requires_approval"), table_name="workflowtask")
    op.drop_index(op.f("ix_workflowtask_priority"), table_name="workflowtask")
    op.drop_table("workflowtask")

