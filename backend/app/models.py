import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import EmailStr
from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore[assignment]
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class WorkflowTaskStatus:
    NEW = "new"
    READY = "ready"
    RUNNING = "running"
    NEEDS_APPROVAL = "needs_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowTaskPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowRiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentScenario:
    KNOWLEDGE = "knowledge"
    WORKFLOW = "workflow"
    CODE = "code"
    ANALYSIS = "analysis"
    EXTERNAL_API = "external_api"
    GENERAL = "general"


class WorkflowTaskBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    objective: str = Field(min_length=1)
    context: str | None = Field(default=None)
    expected_output: str | None = Field(default=None, max_length=500)
    scenario_hint: str | None = Field(default=None, max_length=50, index=True)
    priority: str = Field(default=WorkflowTaskPriority.MEDIUM, max_length=20, index=True)
    status: str = Field(default=WorkflowTaskStatus.NEW, max_length=50, index=True)
    risk_level: str = Field(default=WorkflowRiskLevel.MEDIUM, max_length=20, index=True)
    requires_approval: bool = Field(default=False, index=True)
    owner_team: str | None = Field(default=None, max_length=100)
    final_summary: str | None = Field(default=None)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class WorkflowTaskCreate(WorkflowTaskBase):
    pass


class WorkflowTaskUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    objective: str | None = Field(default=None, min_length=1)
    context: str | None = None
    expected_output: str | None = Field(default=None, max_length=500)
    scenario_hint: str | None = Field(default=None, max_length=50)
    priority: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, max_length=50)
    risk_level: str | None = Field(default=None, max_length=20)
    requires_approval: bool | None = None
    owner_team: str | None = Field(default=None, max_length=100)
    final_summary: str | None = None
    tags: list[str] | None = None


class WorkflowTask(WorkflowTaskBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class WorkflowTaskPublic(WorkflowTaskBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class WorkflowTasksPublic(SQLModel):
    data: list[WorkflowTaskPublic]
    count: int


class AgentRunStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RECOVERED = "recovered"
    NEEDS_HUMAN = "needs_human"
    FAILED = "failed"


class AgentApprovalStatus:
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"


class AgentFailureType:
    NONE = "none"
    PLANNING = "planning_error"
    TOOL_SELECTION = "tool_selection_error"
    RETRIEVAL = "retrieval_error"
    FORMAT = "format_error"
    REASONING = "reasoning_error"
    LOW_CONFIDENCE = "low_confidence"


class AgentRunBase(SQLModel):
    scenario: str = Field(default=AgentScenario.GENERAL, max_length=50, index=True)
    status: str = Field(default=AgentRunStatus.PENDING, max_length=50, index=True)
    failure_type: str = Field(default=AgentFailureType.NONE, max_length=80, index=True)
    recovery_action: str | None = Field(default=None, max_length=255)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reliability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    selected_tool: str | None = Field(default=None, max_length=120)
    final_answer: str | None = Field(default=None)
    run_profile: str = Field(default="aetherflow_reliability_runtime", max_length=80, index=True)
    runtime_version: str = Field(default="aetherflow-runtime-v1", max_length=80, index=True)
    idempotency_key: str | None = Field(default=None, max_length=120, index=True)
    approval_status: str = Field(default=AgentApprovalStatus.NOT_REQUIRED, max_length=30, index=True)
    approval_comment: str | None = Field(default=None, max_length=500)
    approved_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    approved_by: uuid.UUID | None = Field(default=None)
    risk_level: str = Field(default=WorkflowRiskLevel.MEDIUM, max_length=20, index=True)
    graph_node_count: int = Field(default=0, ge=0)
    cost_units: float = Field(default=0.0, ge=0.0)


class AgentRun(AgentRunBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID | None = Field(default=None, foreign_key="workflowtask.id", index=True)
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AgentTraceStepBase(SQLModel):
    sequence: int = Field(index=True)
    stage: str = Field(max_length=80, index=True)
    agent_name: str = Field(max_length=120)
    tool_name: str | None = Field(default=None, max_length=120)
    status: str = Field(default="success", max_length=50, index=True)
    input_snapshot: str | None = None
    output_snapshot: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    latency_ms: int = Field(default=0, ge=0)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )


class AgentTraceStep(AgentTraceStepBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(foreign_key="agentrun.id", nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AgentTraceStepPublic(AgentTraceStepBase):
    id: uuid.UUID
    run_id: uuid.UUID
    created_at: datetime


class AgentRunPublic(AgentRunBase):
    id: uuid.UUID
    task_id: uuid.UUID | None = None
    owner_id: uuid.UUID
    created_at: datetime
    completed_at: datetime | None = None
    steps: list[AgentTraceStepPublic] = Field(default_factory=list)


class AgentRunsPublic(SQLModel):
    data: list[AgentRunPublic]
    count: int


class AgentRunApprovalRequest(SQLModel):
    comment: str | None = Field(default=None, max_length=500)


class ToolDefinitionPublic(SQLModel):
    name: str
    label: str
    scenario: str
    risk_level: str
    avg_latency_ms: int
    success_rate: float
    description: str


class AgentDashboardSummary(SQLModel):
    task_count: int
    active_task_count: int
    approval_queue_count: int
    run_count: int
    success_rate: float
    handled_rate: float
    approval_rate: float
    recovery_rate: float
    average_confidence: float
    average_reliability_score: float
    average_cost_units: float


class OperationsSummary(SQLModel):
    total_tasks: int
    active_tasks: int
    completed_tasks: int
    failed_tasks: int
    approval_queue: int
    total_runs: int
    successful_runs: int
    recovered_runs: int
    failed_runs: int
    success_rate: float
    average_reliability: float


class OperationsQueueItem(SQLModel):
    task_id: uuid.UUID
    run_id: uuid.UUID | None = None
    title: str
    objective: str
    owner_name: str
    owner_email: str
    owner_team: str
    task_status: str
    run_status: str
    scenario: str
    risk_level: str
    selected_tool: str | None = None
    approval_status: str
    reliability_score: float
    created_at: datetime
    completed_at: datetime | None = None


class OperationsTeamSummary(SQLModel):
    team: str
    task_count: int
    active_task_count: int
    run_count: int
    approval_queue_count: int
    success_rate: float
    average_reliability: float


class OperationsDashboard(SQLModel):
    generated_at: datetime = Field(default_factory=get_datetime_utc)
    summary: OperationsSummary
    teams: list[OperationsTeamSummary] = Field(default_factory=list)
    queue: list[OperationsQueueItem] = Field(default_factory=list)


class EvaluationMetric(SQLModel):
    name: str
    single_agent: float
    naive_multi_agent: float
    reliability_harness: float
    unit: str = "ratio"


class EvaluationCaseResult(SQLModel):
    case_id: str
    user_request: str
    expected_tool: str
    selected_tool: str
    top3_tools: list[str] = Field(default_factory=list)
    top5_tools: list[str] = Field(default_factory=list)
    expected_approval: bool
    actual_approval: bool
    expected_scenario: str
    actual_scenario: str
    contract_score: float
    matched_contract_terms: list[str] = Field(default_factory=list)
    missing_contract_terms: list[str] = Field(default_factory=list)
    trace_complete: bool
    result: str
    failure_reason: str | None = None


class EvaluationFailureAnalysis(SQLModel):
    case_id: str
    category: str
    reason: str
    recommendation: str


class EvaluationDatasetInfo(SQLModel):
    dataset_key: str = "sample"
    task_dataset_name: str
    tool_library_name: str
    evaluation_mode: str
    dynamic_tool_count: int
    has_expected_tool: bool
    has_tool_library: bool


class AgentExperiment(SQLModel, table=True):
    id: str = Field(primary_key=True, max_length=80)
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, index=True)
    experiment_name: str = Field(max_length=160)
    dataset_key: str = Field(max_length=40, index=True)
    runtime_version: str = Field(max_length=80)
    status: str = Field(max_length=30, index=True)
    case_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    release_gate_status: str = Field(max_length=20, index=True)
    release_gate_label: str = Field(max_length=30)
    report_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class EvaluationExperimentSummary(SQLModel):
    id: str
    experiment_name: str
    dataset_key: str
    runtime_version: str
    status: str
    case_count: int
    failure_count: int
    release_gate_status: str
    release_gate_label: str
    created_at: datetime


class EvaluationExperimentsPublic(SQLModel):
    data: list[EvaluationExperimentSummary]
    count: int


class EvaluationGateCheck(SQLModel):
    name: str
    score: float
    threshold: float
    passed: bool
    detail: str


class EvaluationReleaseGate(SQLModel):
    status: str
    label: str
    summary: str


class EvaluationScenarioSlice(SQLModel):
    scenario: str
    case_count: int
    pass_rate: float
    top1_accuracy: float
    approval_accuracy: float
    contract_coverage: float
    failed_cases: list[str] = Field(default_factory=list)


class EvaluationToolCoverage(SQLModel):
    tool_name: str
    expected_count: int
    selected_count: int
    top1_hits: int
    accuracy: float
    average_rank: float | None = None


class EvaluationReportPublic(SQLModel):
    generated_at: datetime = Field(default_factory=get_datetime_utc)
    experiment_id: str
    experiment_name: str
    runtime_version: str
    status: str
    sample_size: int
    case_count: int
    failure_count: int
    metrics: list[EvaluationMetric]
    release_gate: EvaluationReleaseGate
    gate_checks: list[EvaluationGateCheck] = Field(default_factory=list)
    scenario_slices: list[EvaluationScenarioSlice] = Field(default_factory=list)
    tool_coverage: list[EvaluationToolCoverage] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    dataset: EvaluationDatasetInfo | None = None
    cases: list[EvaluationCaseResult] = Field(default_factory=list)
    failures: list[EvaluationFailureAnalysis] = Field(default_factory=list)






