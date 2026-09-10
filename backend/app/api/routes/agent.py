import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import and_
from sqlmodel import col, func, select

from app.agent.runtime import runtime
from app.agent.scorers import (
    RunEvaluationPublic,
    RunEvaluationRequest,
    ScorerDefinitionPayload,
    ScorerPreviewRequest,
    ScorerScoreResult,
    evaluate_run,
    list_builtin_scorers,
    preview_scorer,
)
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    AgentApprovalStatus,
    AgentDashboardSummary,
    AgentExperiment,
    AgentRun,
    AgentRunApprovalRequest,
    AgentRunPublic,
    AgentRunsPublic,
    AgentRunStatus,
    AgentTraceStep,
    AgentTraceStepPublic,
    EvaluationExperimentsPublic,
    EvaluationExperimentSummary,
    EvaluationReportPublic,
    ToolDefinitionPublic,
    WorkflowTask,
    WorkflowTaskStatus,
)

router = APIRouter(prefix="/agent", tags=["agent"])


def _ensure_task_access(task: WorkflowTask | None, current_user: CurrentUser) -> WorkflowTask:
    if not task:
        raise HTTPException(status_code=404, detail="Workflow task not found")
    if not current_user.is_superuser and task.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return task


def _ensure_run_access(run: AgentRun | None, current_user: CurrentUser) -> AgentRun:
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    if run.task_id is None:
        raise HTTPException(status_code=404, detail="Agent run belongs to a deprecated demo object")
    if not current_user.is_superuser and run.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return run


def _public_run(session: SessionDep, run: AgentRun) -> AgentRunPublic:
    steps = session.exec(
        select(AgentTraceStep)
        .where(AgentTraceStep.run_id == run.id)
        .order_by(col(AgentTraceStep.sequence))
    ).all()
    return AgentRunPublic(
        **run.model_dump(),
        steps=[AgentTraceStepPublic.model_validate(step) for step in steps],
    )


def _task_filter(current_user: CurrentUser):
    if current_user.is_superuser:
        return True
    return WorkflowTask.owner_id == current_user.id


def _run_filter(current_user: CurrentUser):
    has_task = col(AgentRun.task_id).is_not(None)
    if current_user.is_superuser:
        return has_task
    return and_(AgentRun.owner_id == current_user.id, has_task)


def _experiment_filter(current_user: CurrentUser):
    if current_user.is_superuser:
        return True
    return AgentExperiment.owner_id == current_user.id


@router.get("/scorers", response_model=list[ScorerDefinitionPayload])
def read_scorers(_current_user: CurrentUser) -> list[ScorerDefinitionPayload]:
    return list_builtin_scorers()


@router.post("/runs/{run_id}/evaluate", response_model=RunEvaluationPublic)
def evaluate_agent_run(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    run_id: uuid.UUID,
    payload: RunEvaluationRequest | None = None,
) -> RunEvaluationPublic:
    run = _ensure_run_access(session.get(AgentRun, run_id), current_user)
    task = session.get(WorkflowTask, run.task_id) if run.task_id else None
    steps = session.exec(
        select(AgentTraceStep)
        .where(AgentTraceStep.run_id == run.id)
        .order_by(col(AgentTraceStep.sequence))
    ).all()
    return evaluate_run(
        task=task,
        run=run,
        trace_steps=steps,
        scorer_ids=payload.scorer_ids if payload else None,
    )


@router.post("/scorers/preview", response_model=ScorerScoreResult)
def preview_agent_scorer(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    payload: ScorerPreviewRequest,
) -> ScorerScoreResult:
    run = _ensure_run_access(session.get(AgentRun, payload.run_id), current_user)
    task = session.get(WorkflowTask, run.task_id) if run.task_id else None
    steps = session.exec(
        select(AgentTraceStep)
        .where(AgentTraceStep.run_id == run.id)
        .order_by(col(AgentTraceStep.sequence))
    ).all()
    return preview_scorer(
        definition=payload.definition,
        task=task,
        run=run,
        trace_steps=steps,
    )

@router.get("/tools", response_model=list[ToolDefinitionPublic])
def read_tools(_current_user: CurrentUser) -> list[ToolDefinitionPublic]:
    return runtime.tools()


@router.post("/tasks/{task_id}/runs", response_model=AgentRunPublic)
def run_task_agent(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_id: uuid.UUID,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AgentRunPublic:
    task = _ensure_task_access(session.get(WorkflowTask, task_id), current_user)
    if idempotency_key:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 120:
            raise HTTPException(status_code=422, detail="Idempotency-Key 长度必须为 1 到 120 个字符")
        existing = session.exec(
            select(AgentRun)
            .where(AgentRun.task_id == task.id)
            .where(AgentRun.owner_id == current_user.id)
            .where(AgentRun.idempotency_key == idempotency_key)
        ).first()
        if existing:
            return _public_run(session, existing)
    run = runtime.run_task(
        session=session,
        task=task,
        owner_id=current_user.id,
        idempotency_key=idempotency_key,
    )
    return _public_run(session, run)


@router.get("/tasks/{task_id}/runs", response_model=AgentRunsPublic)
def read_task_runs(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_id: uuid.UUID,
) -> AgentRunsPublic:
    task = _ensure_task_access(session.get(WorkflowTask, task_id), current_user)
    runs = session.exec(
        select(AgentRun)
        .where(AgentRun.task_id == task.id)
        .order_by(col(AgentRun.created_at).desc())
    ).all()
    return AgentRunsPublic(data=[_public_run(session, run) for run in runs], count=len(runs))


@router.get("/runs", response_model=AgentRunsPublic)
def read_agent_runs(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
) -> AgentRunsPublic:
    run_filter = _run_filter(current_user)
    count_statement = select(func.count()).select_from(AgentRun).where(run_filter)
    statement = (
        select(AgentRun)
        .where(run_filter)
        .order_by(col(AgentRun.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    count = session.exec(count_statement).one()
    runs = session.exec(statement).all()
    return AgentRunsPublic(data=[_public_run(session, run) for run in runs], count=count)


@router.get("/runs/{run_id}", response_model=AgentRunPublic)
def read_agent_run(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    run_id: uuid.UUID,
) -> AgentRunPublic:
    run = _ensure_run_access(session.get(AgentRun, run_id), current_user)
    return _public_run(session, run)


@router.post("/runs/{run_id}/approve", response_model=AgentRunPublic)
def approve_agent_run(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    run_id: uuid.UUID,
    payload: AgentRunApprovalRequest | None = None,
) -> AgentRunPublic:
    run = _ensure_run_access(session.get(AgentRun, run_id), current_user)
    try:
        approved_run = runtime.approve_run(
            session=session,
            run=run,
            approver_id=current_user.id,
            comment=payload.comment.strip() if payload and payload.comment else None,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _public_run(session, approved_run)


@router.get("/summary", response_model=AgentDashboardSummary)
def read_agent_summary(
    session: SessionDep,
    current_user: CurrentUser,
) -> AgentDashboardSummary:
    task_filter = _task_filter(current_user)
    run_filter = _run_filter(current_user)

    task_count = session.exec(select(func.count()).select_from(WorkflowTask).where(task_filter)).one()
    active_task_count = session.exec(
        select(func.count())
        .select_from(WorkflowTask)
        .where(task_filter)
        .where(WorkflowTask.status.notin_([WorkflowTaskStatus.COMPLETED, WorkflowTaskStatus.FAILED]))
    ).one()
    approval_queue_count = session.exec(
        select(func.count())
        .select_from(WorkflowTask)
        .where(task_filter)
        .where(WorkflowTask.status == WorkflowTaskStatus.NEEDS_APPROVAL)
    ).one()
    run_count = session.exec(select(func.count()).select_from(AgentRun).where(run_filter)).one()
    success_count = session.exec(
        select(func.count())
        .select_from(AgentRun)
        .where(run_filter)
        .where(AgentRun.status.in_([AgentRunStatus.SUCCEEDED, AgentRunStatus.RECOVERED]))
    ).one()
    handled_count = session.exec(
        select(func.count())
        .select_from(AgentRun)
        .where(run_filter)
        .where(
            AgentRun.status.in_(
                [AgentRunStatus.SUCCEEDED, AgentRunStatus.RECOVERED, AgentRunStatus.NEEDS_HUMAN]
            )
        )
    ).one()
    approval_count = session.exec(
        select(func.count())
        .select_from(AgentRun)
        .where(run_filter)
        .where(AgentRun.approval_status.in_([AgentApprovalStatus.PENDING, AgentApprovalStatus.APPROVED]))
    ).one()
    recovery_count = session.exec(
        select(func.count())
        .select_from(AgentRun)
        .where(run_filter)
        .where(AgentRun.status == AgentRunStatus.RECOVERED)
    ).one()
    avg_confidence = session.exec(
        select(func.avg(AgentRun.confidence)).select_from(AgentRun).where(run_filter)
    ).one()
    avg_reliability = session.exec(
        select(func.avg(AgentRun.reliability_score)).select_from(AgentRun).where(run_filter)
    ).one()
    avg_cost = session.exec(
        select(func.avg(AgentRun.cost_units)).select_from(AgentRun).where(run_filter)
    ).one()

    return AgentDashboardSummary(
        task_count=task_count,
        active_task_count=active_task_count,
        approval_queue_count=approval_queue_count,
        run_count=run_count,
        success_rate=round(success_count / run_count, 2) if run_count else 0.0,
        handled_rate=round(handled_count / run_count, 2) if run_count else 0.0,
        approval_rate=round(approval_count / run_count, 2) if run_count else 0.0,
        recovery_rate=round(recovery_count / run_count, 2) if run_count else 0.0,
        average_confidence=round(float(avg_confidence or 0.0), 2),
        average_reliability_score=round(float(avg_reliability or 0.0), 2),
        average_cost_units=round(float(avg_cost or 0.0), 2),
    )


@router.post("/evaluation/run", response_model=EvaluationReportPublic)
def run_evaluation(
    session: SessionDep,
    current_user: CurrentUser,
    dataset: str = "sample",
) -> EvaluationReportPublic:
    sample_size = session.exec(
        select(func.count()).select_from(AgentRun).where(_run_filter(current_user))
    ).one()
    report = runtime.evaluation_report(sample_size=sample_size, dataset=dataset)
    session.add(
        AgentExperiment(
            id=report.experiment_id,
            owner_id=current_user.id,
            experiment_name=report.experiment_name,
            dataset_key=report.dataset.dataset_key if report.dataset else dataset,
            runtime_version=report.runtime_version,
            status=report.status,
            case_count=report.case_count,
            failure_count=report.failure_count,
            release_gate_status=report.release_gate.status,
            release_gate_label=report.release_gate.label,
            report_json=report.model_dump(mode="json"),
        )
    )
    session.commit()
    return report


@router.get("/experiments", response_model=EvaluationExperimentsPublic)
def read_experiments(
    session: SessionDep,
    current_user: CurrentUser,
) -> EvaluationExperimentsPublic:
    experiments = session.exec(
        select(AgentExperiment)
        .where(_experiment_filter(current_user))
        .order_by(col(AgentExperiment.created_at).desc())
        .limit(20)
    ).all()
    return EvaluationExperimentsPublic(
        data=[EvaluationExperimentSummary.model_validate(experiment) for experiment in experiments],
        count=len(experiments),
    )


@router.get("/experiments/{experiment_id}", response_model=EvaluationReportPublic)
def read_experiment(
    experiment_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> EvaluationReportPublic:
    experiment = session.get(AgentExperiment, experiment_id)
    if not experiment or (not current_user.is_superuser and experiment.owner_id != current_user.id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    return EvaluationReportPublic.model_validate(experiment.report_json)



