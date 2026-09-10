import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    WorkflowTask,
    WorkflowTaskCreate,
    WorkflowTaskPublic,
    WorkflowTasksPublic,
    WorkflowTaskUpdate,
)

router = APIRouter()


def _ensure_task_access(task: WorkflowTask | None, current_user: CurrentUser) -> WorkflowTask:
    if not task:
        raise HTTPException(status_code=404, detail="Workflow task not found")
    if not current_user.is_superuser and task.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return task


@router.get("/", response_model=WorkflowTasksPublic)
def read_workflow_tasks(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> WorkflowTasksPublic:
    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(WorkflowTask)
        statement = select(WorkflowTask).order_by(col(WorkflowTask.created_at).desc())
    else:
        count_statement = (
            select(func.count())
            .select_from(WorkflowTask)
            .where(WorkflowTask.owner_id == current_user.id)
        )
        statement = (
            select(WorkflowTask)
            .where(WorkflowTask.owner_id == current_user.id)
            .order_by(col(WorkflowTask.created_at).desc())
        )

    count = session.exec(count_statement).one()
    tasks = session.exec(statement.offset(skip).limit(limit)).all()
    return WorkflowTasksPublic(data=tasks, count=count)


@router.post("/", response_model=WorkflowTaskPublic)
def create_workflow_task(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_in: WorkflowTaskCreate,
) -> WorkflowTask:
    task = WorkflowTask.model_validate(task_in, update={"owner_id": current_user.id})
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.get("/{task_id}", response_model=WorkflowTaskPublic)
def read_workflow_task(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_id: uuid.UUID,
) -> WorkflowTask:
    return _ensure_task_access(session.get(WorkflowTask, task_id), current_user)


@router.patch("/{task_id}", response_model=WorkflowTaskPublic)
def update_workflow_task(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_id: uuid.UUID,
    task_in: WorkflowTaskUpdate,
) -> WorkflowTask:
    task = _ensure_task_access(session.get(WorkflowTask, task_id), current_user)
    update_data = task_in.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)
    task.sqlmodel_update(update_data)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}")
def delete_workflow_task(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_id: uuid.UUID,
) -> Message:
    task = _ensure_task_access(session.get(WorkflowTask, task_id), current_user)
    session.delete(task)
    session.commit()
    return Message(message="Workflow task deleted successfully")
