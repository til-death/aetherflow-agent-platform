"""Add FlowCare tickets and agent runtime tables

Revision ID: b83f2a6d41c2
Revises: fe56fa70289e
Create Date: 2026-06-23 11:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "b83f2a6d41c2"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ticket",
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("customer_name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column("order_id", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ticket_type", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("priority", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("need_human", sa.Boolean(), nullable=False),
        sa.Column("assigned_group", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column("ai_summary", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ticket_order_id"), "ticket", ["order_id"], unique=False)
    op.create_index(op.f("ix_ticket_priority"), "ticket", ["priority"], unique=False)
    op.create_index(op.f("ix_ticket_status"), "ticket", ["status"], unique=False)
    op.create_index(op.f("ix_ticket_ticket_type"), "ticket", ["ticket_type"], unique=False)
    op.create_index(op.f("ix_ticket_need_human"), "ticket", ["need_human"], unique=False)

    op.create_table(
        "agentrun",
        sa.Column("scenario", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("failure_type", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("recovery_action", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reliability_score", sa.Float(), nullable=False),
        sa.Column("selected_tool", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
        sa.Column("final_answer", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("run_profile", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agentrun_failure_type"), "agentrun", ["failure_type"], unique=False)
    op.create_index(op.f("ix_agentrun_owner_id"), "agentrun", ["owner_id"], unique=False)
    op.create_index(op.f("ix_agentrun_run_profile"), "agentrun", ["run_profile"], unique=False)
    op.create_index(op.f("ix_agentrun_scenario"), "agentrun", ["scenario"], unique=False)
    op.create_index(op.f("ix_agentrun_status"), "agentrun", ["status"], unique=False)
    op.create_index(op.f("ix_agentrun_ticket_id"), "agentrun", ["ticket_id"], unique=False)

    op.create_table(
        "agenttracestep",
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("stage", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("agent_name", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("tool_name", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("input_snapshot", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("output_snapshot", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agentrun.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agenttracestep_run_id"), "agenttracestep", ["run_id"], unique=False)
    op.create_index(op.f("ix_agenttracestep_sequence"), "agenttracestep", ["sequence"], unique=False)
    op.create_index(op.f("ix_agenttracestep_stage"), "agenttracestep", ["stage"], unique=False)
    op.create_index(op.f("ix_agenttracestep_status"), "agenttracestep", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_agenttracestep_status"), table_name="agenttracestep")
    op.drop_index(op.f("ix_agenttracestep_stage"), table_name="agenttracestep")
    op.drop_index(op.f("ix_agenttracestep_sequence"), table_name="agenttracestep")
    op.drop_index(op.f("ix_agenttracestep_run_id"), table_name="agenttracestep")
    op.drop_table("agenttracestep")

    op.drop_index(op.f("ix_agentrun_ticket_id"), table_name="agentrun")
    op.drop_index(op.f("ix_agentrun_status"), table_name="agentrun")
    op.drop_index(op.f("ix_agentrun_scenario"), table_name="agentrun")
    op.drop_index(op.f("ix_agentrun_run_profile"), table_name="agentrun")
    op.drop_index(op.f("ix_agentrun_owner_id"), table_name="agentrun")
    op.drop_index(op.f("ix_agentrun_failure_type"), table_name="agentrun")
    op.drop_table("agentrun")

    op.drop_index(op.f("ix_ticket_need_human"), table_name="ticket")
    op.drop_index(op.f("ix_ticket_ticket_type"), table_name="ticket")
    op.drop_index(op.f("ix_ticket_status"), table_name="ticket")
    op.drop_index(op.f("ix_ticket_priority"), table_name="ticket")
    op.drop_index(op.f("ix_ticket_order_id"), table_name="ticket")
    op.drop_table("ticket")
