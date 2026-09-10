from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import (
    AgentScenario,
    User,
    UserCreate,
    WorkflowRiskLevel,
    WorkflowTask,
    WorkflowTaskPriority,
    WorkflowTaskStatus,
)

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)

    existing_task = session.exec(select(WorkflowTask)).first()
    if not existing_task:
        demo_tasks = [
            WorkflowTask(
                title="Diagnose why Project Atlas onboarding is blocked",
                objective="Find the likely blocker across policy notes, dependency graph, and workflow state, then produce an auditable handoff plan.",
                context="Atlas depends on security review, CRM workspace provisioning, and finance approval. SLA checkpoint is tomorrow.",
                expected_output="Root-cause summary, evidence path, owner handoff, and next checkpoint.",
                scenario_hint=AgentScenario.WORKFLOW,
                priority=WorkflowTaskPriority.HIGH,
                status=WorkflowTaskStatus.READY,
                risk_level=WorkflowRiskLevel.MEDIUM,
                owner_team="workflow-ops",
                tags=["workflow", "sla", "dependency"],
                owner_id=user.id,
            ),
            WorkflowTask(
                title="Explain revenue anomaly in the enterprise dashboard",
                objective="Profile the metric shift, separate data quality from real business change, and propose the next analysis step.",
                context="CSV export shows a 23 percent drop in expansion revenue for one segment after a dashboard schema change.",
                expected_output="Data quality checks, likely cause labels, and owner follow-up plan.",
                scenario_hint=AgentScenario.ANALYSIS,
                priority=WorkflowTaskPriority.MEDIUM,
                status=WorkflowTaskStatus.READY,
                risk_level=WorkflowRiskLevel.MEDIUM,
                owner_team="data-ops",
                tags=["analysis", "metric", "csv"],
                owner_id=user.id,
            ),
            WorkflowTask(
                title="Prepare a safe reconciliation script dry run",
                objective="Plan a Python dry run to reconcile invoice IDs against contract records without touching production data.",
                context="The operator needs code execution, but filesystem and network access must stay blocked.",
                expected_output="Sandbox execution plan, dry-run assumptions, and traceable output contract.",
                scenario_hint=AgentScenario.CODE,
                priority=WorkflowTaskPriority.HIGH,
                status=WorkflowTaskStatus.READY,
                risk_level=WorkflowRiskLevel.HIGH,
                requires_approval=True,
                owner_team="automation-platform",
                tags=["sandbox", "python", "finance"],
                owner_id=user.id,
            ),
            WorkflowTask(
                title="Draft external CRM update for renewal risk",
                objective="Validate the external action schema and prepare an idempotent CRM update plan for a renewal-risk account.",
                context="This is customer-visible and should not mutate CRM until approval is granted.",
                expected_output="API contract, approval checkpoint, rollback note, and final mutation payload outline.",
                scenario_hint=AgentScenario.EXTERNAL_API,
                priority=WorkflowTaskPriority.CRITICAL,
                status=WorkflowTaskStatus.READY,
                risk_level=WorkflowRiskLevel.HIGH,
                requires_approval=True,
                owner_team="integration-ops",
                tags=["api", "crm", "approval"],
                owner_id=user.id,
            ),
        ]
        session.add_all(demo_tasks)
        session.commit()
