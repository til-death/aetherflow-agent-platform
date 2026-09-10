from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlmodel import col, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.models import (
    AgentApprovalStatus,
    AgentRun,
    AgentRunStatus,
    AgentScenario,
    OperationsDashboard,
    OperationsQueueItem,
    OperationsSummary,
    OperationsTeamSummary,
    User,
    WorkflowRiskLevel,
    WorkflowTask,
    WorkflowTaskStatus,
)

router = APIRouter(
    prefix="/operations",
    tags=["operations"],
    dependencies=[Depends(get_current_active_superuser)],
)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 2) if denominator else 0.0


def _owner_name(user: User | None) -> str:
    if not user:
        return "未知成员"
    return user.full_name or str(user.email).split("@", maxsplit=1)[0]


def _team_name(task: WorkflowTask) -> str:
    return task.owner_team or "未分配"


@router.get("/dashboard", response_model=OperationsDashboard)
def read_operations_dashboard(
    session: SessionDep,
    team: str | None = None,
    status: str | None = None,
    limit: int = 25,
) -> OperationsDashboard:
    """Return the company-level work queue and operational aggregates."""
    limit = min(max(limit, 1), 100)
    tasks = session.exec(
        select(WorkflowTask).order_by(col(WorkflowTask.created_at).desc())
    ).all()
    runs = session.exec(
        select(AgentRun)
        .where(col(AgentRun.task_id).is_not(None))
        .order_by(col(AgentRun.created_at).desc())
    ).all()
    users = {user.id: user for user in session.exec(select(User)).all()}

    filtered_tasks = [task for task in tasks if not team or _team_name(task) == team]
    task_ids = {task.id for task in filtered_tasks}
    filtered_runs = [run for run in runs if run.task_id in task_ids]
    task_by_id = {task.id: task for task in filtered_tasks}

    successful_runs = sum(
        run.status in (AgentRunStatus.SUCCEEDED, AgentRunStatus.RECOVERED)
        for run in filtered_runs
    )
    completed_tasks = sum(task.status == WorkflowTaskStatus.COMPLETED for task in filtered_tasks)
    failed_tasks = sum(task.status == WorkflowTaskStatus.FAILED for task in filtered_tasks)
    active_tasks = sum(
        task.status not in (WorkflowTaskStatus.COMPLETED, WorkflowTaskStatus.FAILED)
        for task in filtered_tasks
    )
    approval_queue = sum(
        run.approval_status == AgentApprovalStatus.PENDING for run in filtered_runs
    )
    average_reliability = (
        round(sum(run.reliability_score for run in filtered_runs) / len(filtered_runs), 2)
        if filtered_runs
        else 0.0
    )

    team_names = sorted({_team_name(task) for task in filtered_tasks})
    teams: list[OperationsTeamSummary] = []
    for team_name in team_names:
        team_tasks = [task for task in filtered_tasks if _team_name(task) == team_name]
        team_task_ids = {task.id for task in team_tasks}
        team_runs = [run for run in filtered_runs if run.task_id in team_task_ids]
        team_successes = sum(
            run.status in (AgentRunStatus.SUCCEEDED, AgentRunStatus.RECOVERED)
            for run in team_runs
        )
        teams.append(
            OperationsTeamSummary(
                team=team_name,
                task_count=len(team_tasks),
                active_task_count=sum(
                    task.status not in (WorkflowTaskStatus.COMPLETED, WorkflowTaskStatus.FAILED)
                    for task in team_tasks
                ),
                run_count=len(team_runs),
                approval_queue_count=sum(
                    run.approval_status == AgentApprovalStatus.PENDING for run in team_runs
                ),
                success_rate=_rate(team_successes, len(team_runs)),
                average_reliability=(
                    round(sum(run.reliability_score for run in team_runs) / len(team_runs), 2)
                    if team_runs
                    else 0.0
                ),
            )
        )

    queue: list[OperationsQueueItem] = []
    queue_runs = [run for run in filtered_runs if not status or run.status == status]
    for run in queue_runs[:limit]:
        task = task_by_id.get(run.task_id)
        if not task:
            continue
        owner = users.get(task.owner_id) or users.get(run.owner_id)
        queue.append(
            OperationsQueueItem(
                task_id=task.id,
                run_id=run.id,
                title=task.title,
                objective=task.objective,
                owner_name=_owner_name(owner),
                owner_email=str(owner.email) if owner else "-",
                owner_team=_team_name(task),
                task_status=task.status,
                run_status=run.status,
                scenario=run.scenario or AgentScenario.GENERAL,
                risk_level=run.risk_level or WorkflowRiskLevel.MEDIUM,
                selected_tool=run.selected_tool,
                approval_status=run.approval_status,
                reliability_score=run.reliability_score,
                created_at=run.created_at,
                completed_at=run.completed_at,
            )
        )

    if not status or status == "not_started":
        for task in filtered_tasks:
            if len(queue) >= limit or task.id in {run.task_id for run in filtered_runs}:
                continue
            owner = users.get(task.owner_id)
            queue.append(
                OperationsQueueItem(
                    task_id=task.id,
                    title=task.title,
                    objective=task.objective,
                    owner_name=_owner_name(owner),
                    owner_email=str(owner.email) if owner else "-",
                    owner_team=_team_name(task),
                    task_status=task.status,
                    run_status="not_started",
                    scenario=task.scenario_hint or AgentScenario.GENERAL,
                    risk_level=task.risk_level or WorkflowRiskLevel.MEDIUM,
                    approval_status=AgentApprovalStatus.NOT_REQUIRED,
                    reliability_score=0.0,
                    created_at=task.created_at,
                )
            )

    return OperationsDashboard(
        generated_at=datetime.now(timezone.utc),
        summary=OperationsSummary(
            total_tasks=len(filtered_tasks),
            active_tasks=active_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            approval_queue=approval_queue,
            total_runs=len(filtered_runs),
            successful_runs=successful_runs,
            recovered_runs=sum(run.status == AgentRunStatus.RECOVERED for run in filtered_runs),
            failed_runs=sum(run.status == AgentRunStatus.FAILED for run in filtered_runs),
            success_rate=_rate(successful_runs, len(filtered_runs)),
            average_reliability=average_reliability,
        ),
        teams=teams,
        queue=queue,
    )
