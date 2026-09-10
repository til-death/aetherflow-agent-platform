from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AgentName = Literal[
    "PlannerAgent",
    "ScenarioRouter",
    "RAGAgent",
    "ToolRouter",
    "ExecutorAgent",
    "CriticAgent",
    "MemoryAgent",
    "RecoveryEngine",
]
ScenarioName = Literal["knowledge", "workflow", "code", "analysis", "external_api", "general"]
RiskLevel = Literal["low", "medium", "high"]
CriticOutcome = Literal[
    "runtime_execution_ready",
    "approval_checkpoint_required",
    "needs_replan",
    "failed",
]


class ExecutionNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,60}$")
    description: str = Field(min_length=8, max_length=500)
    agent: AgentName
    scenario: ScenarioName
    depends_on: list[str] = Field(default_factory=list, max_length=8)
    expected_output_type: str = Field(min_length=3, max_length=80)
    risk_level: RiskLevel
    allowed_tools: list[str] = Field(default_factory=list, max_length=6)


class ExecutionGraphPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective_summary: str = Field(min_length=8, max_length=500)
    nodes: list[ExecutionNode] = Field(min_length=4, max_length=12)
    assumptions: list[str] = Field(default_factory=list, max_length=8)
    missing_context: list[str] = Field(default_factory=list, max_length=8)
    estimated_risk: RiskLevel


class CriticDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: CriticOutcome
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    needs_approval: bool
    blockers: list[str] = Field(default_factory=list, max_length=12)
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    hallucination_risk: float = Field(ge=0.0, le=1.0)
    recommended_recovery: str | None = Field(default=None, max_length=255)

