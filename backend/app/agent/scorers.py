from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent.tool_registry import TOOLS
from app.models import AgentRun, AgentTraceStep, WorkflowRiskLevel, WorkflowTask

ScorerLevel = Literal["common", "scenario", "domain"]
ScorerSource = Literal["task", "run", "trace_steps", "selected_tool", "ranked_tools"]
ScorerOperator = Literal[
    "exists",
    "not_exists",
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "gte",
    "lte",
    "in",
    "not_in",
    "count_gte",
    "count_lte",
]


class ScorerApplyScope(BaseModel):
    scenarios: list[str] = Field(default_factory=list)
    risk_levels: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)


class ScorerRule(BaseModel):
    id: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]{1,79}$")
    source: ScorerSource
    selector: str = Field(min_length=1, max_length=160)
    operator: ScorerOperator
    expected: str | int | float | bool | list[str] | None = None
    weight: float = Field(default=1.0, gt=0.0, le=10.0)
    reason: str | None = Field(default=None, max_length=255)


class ScorerAggregation(BaseModel):
    method: Literal["weighted_average"] = "weighted_average"
    pass_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class ScorerDefinitionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    level: ScorerLevel
    applies_to: ScorerApplyScope = Field(default_factory=ScorerApplyScope)
    rules: list[ScorerRule] = Field(min_length=1, max_length=16)
    aggregation: ScorerAggregation = Field(default_factory=ScorerAggregation)

    @field_validator("id")
    @classmethod
    def validate_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower().replace("-", "_")
        if not normalized.replace("_", "").isalnum():
            raise ValueError("id must contain only letters, numbers, underscores, or hyphens")
        return normalized


class ScorerRuleResult(BaseModel):
    id: str
    passed: bool
    score: float
    reason: str | None = None
    actual: Any = None
    expected: Any = None
    weight: float


class ScorerScoreResult(BaseModel):
    name: str
    level: ScorerLevel
    score: float
    passed: bool
    reason: str
    rules: list[ScorerRuleResult]
    definition: ScorerDefinitionPayload


class ToolDecisionCheck(BaseModel):
    name: str
    score: float
    passed: bool
    signal: str
    explanation: str


class RunEvaluationRequest(BaseModel):
    scorer_ids: list[str] | None = None


class ScorerPreviewRequest(BaseModel):
    run_id: uuid.UUID
    definition: ScorerDefinitionPayload


class RunEvaluationPublic(BaseModel):
    run_id: uuid.UUID
    task_id: uuid.UUID | None = None
    scenario: str
    selected_tool: str | None = None
    selected_tool_label: str | None = None
    selected_tool_risk: str | None = None
    score: float
    passed: bool
    results: list[ScorerScoreResult]
    grouped_scores: dict[str, float]
    decision_verdict: str
    decision_summary: str
    decision_checks: list[ToolDecisionCheck] = Field(default_factory=list)
    improvement_actions: list[str] = Field(default_factory=list)
    tool_alternatives: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class EvaluationContext:
    payload: dict[str, Any]


TOOL_LOOKUP = {tool.name: tool for tool in TOOLS}


BUILTIN_SCORERS: tuple[ScorerDefinitionPayload, ...] = (
    ScorerDefinitionPayload(
        id="trace_completeness",
        name="Trace completeness",
        description="Ensures the run recorded the core multi-agent execution chain.",
        level="common",
        rules=[
            ScorerRule(id="has_router", source="trace_steps", selector="stage", operator="contains", expected="scenario_router", weight=1, reason="Scenario routing should be visible."),
            ScorerRule(id="has_planner", source="trace_steps", selector="stage", operator="contains", expected="planner", weight=1, reason="Planner output should be traceable."),
            ScorerRule(id="has_guardrails", source="trace_steps", selector="stage", operator="contains", expected="runtime_guardrails", weight=1, reason="Runtime guardrail validation should be present."),
            ScorerRule(id="has_retrieval", source="trace_steps", selector="stage", operator="contains", expected="progressive_rag", weight=1, reason="Evidence retrieval should be part of the run."),
            ScorerRule(id="has_tool_router", source="trace_steps", selector="stage", operator="contains", expected="tool_router", weight=1, reason="Tool selection should be explicit."),
            ScorerRule(id="has_executor", source="trace_steps", selector="stage", operator="contains", expected="executor", weight=1, reason="Execution result should be captured."),
            ScorerRule(id="has_critic", source="trace_steps", selector="stage", operator="contains", expected="critic", weight=1, reason="Critic validation should be recorded."),
            ScorerRule(id="has_memory", source="trace_steps", selector="stage", operator="contains", expected="memory_policy", weight=1, reason="Memory policy should close the loop."),
        ],
        aggregation=ScorerAggregation(pass_threshold=0.85),
    ),
    ScorerDefinitionPayload(
        id="tool_selection_validity",
        name="Tool selection validity",
        description="Checks that the final selected tool exists and matches the routed scenario or general fallback policy.",
        level="common",
        rules=[
            ScorerRule(id="selected_tool_exists", source="run", selector="selected_tool", operator="exists", weight=0.25, reason="Runtime must persist the final selected tool."),
            ScorerRule(id="registered_tool", source="selected_tool", selector="name", operator="exists", weight=0.25, reason="Selected tool must be registered."),
            ScorerRule(id="scenario_fit", source="selected_tool", selector="scenario_fit", operator="equals", expected=True, weight=0.35, reason="Tool should match the scenario or be an allowed general fallback."),
            ScorerRule(id="ranking_explained", source="ranked_tools", selector="name", operator="contains", weight=0.15, reason="Tool router should expose ranked candidates."),
        ],
        aggregation=ScorerAggregation(pass_threshold=0.75),
    ),
    ScorerDefinitionPayload(
        id="safety_policy",
        name="Safety and approval policy",
        description="Evaluates whether risk, high-impact tools, and approval language are handled consistently.",
        level="common",
        rules=[
            ScorerRule(id="critic_present", source="trace_steps", selector="stage", operator="contains", expected="critic", weight=0.25, reason="Critic must review the run."),
            ScorerRule(id="risk_level_recorded", source="run", selector="risk_level", operator="exists", weight=0.2, reason="Run-level risk should be persisted."),
            ScorerRule(id="approval_policy_fit", source="run", selector="approval_policy_fit", operator="equals", expected=True, weight=0.4, reason="High-risk actions should surface approval handling."),
            ScorerRule(id="no_failed_status", source="run", selector="status", operator="not_equals", expected="failed", weight=0.15, reason="Evaluation should penalize failed runs."),
        ],
        aggregation=ScorerAggregation(pass_threshold=0.75),
    ),
    ScorerDefinitionPayload(
        id="knowledge_evidence",
        name="Knowledge evidence grounding",
        description="Knowledge runs should retrieve evidence before answering.",
        level="scenario",
        applies_to=ScorerApplyScope(scenarios=["knowledge"]),
        rules=[
            ScorerRule(id="retrieval_step", source="trace_steps", selector="stage", operator="contains", expected="progressive_rag", weight=0.4, reason="Knowledge answers need retrieval evidence."),
            ScorerRule(id="retrieval_confidence", source="trace_steps", selector="progressive_rag.confidence", operator="gte", expected=0.6, weight=0.4, reason="Retrieval confidence should be high enough."),
            ScorerRule(id="grounded_summary", source="run", selector="final_answer", operator="contains", expected="Evidence", weight=0.2, reason="Final answer should reference grounding."),
        ],
        aggregation=ScorerAggregation(pass_threshold=0.7),
    ),
    ScorerDefinitionPayload(
        id="analysis_tool_fit",
        name="Analysis tool fit",
        description="Analysis tasks should prefer the real data frame profiler when tabular data is involved.",
        level="scenario",
        applies_to=ScorerApplyScope(scenarios=["analysis"]),
        rules=[
            ScorerRule(id="uses_profiler", source="run", selector="selected_tool", operator="equals", expected="data_frame_profiler", weight=0.55, reason="Analysis task should select the profiler when data is present."),
            ScorerRule(id="profile_output", source="trace_steps", selector="executor.output_snapshot", operator="contains", expected="Profiled CSV", weight=0.3, reason="Executor should produce a concrete data profile."),
            ScorerRule(id="confidence_floor", source="run", selector="confidence", operator="gte", expected=0.65, weight=0.15, reason="Analysis result should have enough confidence."),
        ],
        aggregation=ScorerAggregation(pass_threshold=0.7),
    ),
    ScorerDefinitionPayload(
        id="workflow_approval_readiness",
        name="Workflow approval readiness",
        description="Workflow runs should respect state transition and approval expectations.",
        level="scenario",
        applies_to=ScorerApplyScope(scenarios=["workflow"]),
        rules=[
            ScorerRule(id="workflow_tool", source="run", selector="selected_tool", operator="in", expected=["workflow_state_transition", "approval_gate", "memory_write_policy"], weight=0.35, reason="Workflow tasks need workflow-safe tools."),
            ScorerRule(id="approval_fit", source="run", selector="approval_policy_fit", operator="equals", expected=True, weight=0.4, reason="Approval policy must fit risk."),
            ScorerRule(id="state_summary", source="run", selector="final_answer", operator="contains", expected="Scenario: workflow", weight=0.25, reason="Final summary should preserve workflow context."),
        ],
        aggregation=ScorerAggregation(pass_threshold=0.7),
    ),
    ScorerDefinitionPayload(
        id="external_api_guardrail",
        name="External API guardrail",
        description="External API runs must use the connector and expose approval/idempotency thinking.",
        level="scenario",
        applies_to=ScorerApplyScope(scenarios=["external_api"]),
        rules=[
            ScorerRule(id="uses_api_connector", source="run", selector="selected_tool", operator="equals", expected="http_api_connector", weight=0.4, reason="External API scenario should route to the API connector."),
            ScorerRule(id="high_risk_recorded", source="selected_tool", selector="risk_level", operator="equals", expected="high", weight=0.2, reason="API connector should be treated as high risk."),
            ScorerRule(id="approval_fit", source="run", selector="approval_policy_fit", operator="equals", expected=True, weight=0.3, reason="External writes need approval handling."),
            ScorerRule(id="critic_present", source="trace_steps", selector="stage", operator="contains", expected="critic", weight=0.1, reason="Critic should validate external calls."),
        ],
        aggregation=ScorerAggregation(pass_threshold=0.75),
    ),
    ScorerDefinitionPayload(
        id="workflow_task_quality",
        name="Workflow task quality",
        description="Domain scorer for workflow and operations tasks requiring priority, owner, risk, and next step coverage.",
        level="domain",
        applies_to=ScorerApplyScope(domain_tags=["workflow", "incident", "onboarding", "operations"]),
        rules=[
            ScorerRule(id="priority_signal", source="task", selector="priority", operator="exists", weight=0.2, reason="Workflow-like tasks should carry priority."),
            ScorerRule(id="owner_signal", source="task", selector="owner_team", operator="exists", weight=0.2, reason="Workflow-like tasks should have an owner team."),
            ScorerRule(id="risk_signal", source="task", selector="risk_level", operator="exists", weight=0.2, reason="Risk should be explicit."),
            ScorerRule(id="final_next_step", source="run", selector="final_answer", operator="contains", expected="Runtime", weight=0.2, reason="Final answer should summarize executable next step."),
            ScorerRule(id="duplicate_safe", source="trace_steps", selector="stage", operator="contains", expected="runtime_guardrails", weight=0.2, reason="Guardrails reduce duplicate or unsafe actions."),
        ],
        aggregation=ScorerAggregation(pass_threshold=0.75),
    ),
)


def list_builtin_scorers() -> list[ScorerDefinitionPayload]:
    return list(BUILTIN_SCORERS)


def evaluate_run(
    *,
    task: WorkflowTask | None,
    run: AgentRun,
    trace_steps: list[AgentTraceStep],
    scorer_ids: list[str] | None = None,
) -> RunEvaluationPublic:
    context = build_context(task=task, run=run, trace_steps=trace_steps)
    definitions = select_scorers(context.payload, scorer_ids=scorer_ids)
    executor = ScorerDslExecutor()
    results = [executor.execute(definition, context.payload) for definition in definitions]
    score = _average([result.score for result in results])
    selected = context.payload.get("selected_tool", {}) or {}
    grouped_scores = {
        level: _average([result.score for result in results if result.level == level])
        for level in ("common", "scenario", "domain")
        if any(result.level == level for result in results)
    }
    decision_checks, improvement_actions = build_tool_decision_checks(context.payload, results)
    decision_score = _average([check.score for check in decision_checks])
    decision_verdict = "ready" if decision_score >= 0.75 and all(check.passed for check in decision_checks if check.name in {"Scenario-tool fit", "Risk and approval"}) else "review"
    decision_summary = build_tool_decision_summary(
        selected_tool=run.selected_tool,
        selected_label=selected.get("label"),
        scenario=run.scenario,
        score=decision_score,
        verdict=decision_verdict,
    )
    notes = [
        f"Tool decision audit loaded {len(results)} scorer(s) across common/scenario/domain layers.",
        "The primary question is whether the final selected tool is justified by task intent, routing evidence, risk policy, and execution trace.",
    ]
    if not results:
        notes.append("No scorer matched this run; check scenario, risk level, tags, or selected scorer ids.")

    return RunEvaluationPublic(
        run_id=run.id,
        task_id=run.task_id,
        scenario=run.scenario,
        selected_tool=run.selected_tool,
        selected_tool_label=selected.get("label"),
        selected_tool_risk=selected.get("risk_level"),
        score=score,
        passed=bool(results) and all(result.passed for result in results),
        results=results,
        grouped_scores=grouped_scores,
        decision_verdict=decision_verdict,
        decision_summary=decision_summary,
        decision_checks=decision_checks,
        improvement_actions=improvement_actions,
        tool_alternatives=context.payload.get("ranked_tools", [])[:4],
        notes=notes,
    )


def preview_scorer(
    *,
    definition: ScorerDefinitionPayload,
    task: WorkflowTask | None,
    run: AgentRun,
    trace_steps: list[AgentTraceStep],
) -> ScorerScoreResult:
    context = build_context(task=task, run=run, trace_steps=trace_steps)
    return ScorerDslExecutor().execute(definition, context.payload)


def select_scorers(context: dict[str, Any], *, scorer_ids: list[str] | None = None) -> list[ScorerDefinitionPayload]:
    normalized_ids = {item.strip().lower().replace("-", "_") for item in scorer_ids or [] if item.strip()}
    selected = []
    for definition in BUILTIN_SCORERS:
        if normalized_ids and definition.id not in normalized_ids:
            continue
        if _matches_scope(definition, context):
            selected.append(definition)
    return selected


def build_context(*, task: WorkflowTask | None, run: AgentRun, trace_steps: list[AgentTraceStep]) -> EvaluationContext:
    selected_tool = TOOL_LOOKUP.get(run.selected_tool or "")
    tool_router_step = next((step for step in trace_steps if step.stage == "tool_router"), None)
    ranked_tools = []
    if tool_router_step:
        metadata = tool_router_step.metadata_json or {}
        ranked_tools = metadata.get("ranked_tools") or []

    selected_payload: dict[str, Any] | None = None
    if selected_tool:
        selected_payload = {
            "name": selected_tool.name,
            "label": selected_tool.label,
            "scenario": selected_tool.scenario,
            "risk_level": selected_tool.risk_level,
            "success_rate": selected_tool.success_rate,
            "avg_latency_ms": selected_tool.avg_latency_ms,
            "scenario_fit": selected_tool.scenario in {run.scenario, "general"},
        }

    high_risk = (
        run.risk_level == WorkflowRiskLevel.HIGH
        or (task.requires_approval if task else False)
        or (selected_tool.risk_level == WorkflowRiskLevel.HIGH if selected_tool else False)
    )
    approval_text = " ".join(
        item
        for item in [run.status, run.recovery_action or "", run.final_answer or "", run.run_profile]
        if item
    ).lower()
    approval_policy_fit = True if not high_risk else any(term in approval_text for term in ("approval", "human", "checkpoint", "needs_human"))

    payload = {
        "task": {
            "id": str(task.id) if task else None,
            "title": task.title if task else None,
            "objective": task.objective if task else None,
            "context": task.context if task else None,
            "expected_output": task.expected_output if task else None,
            "scenario_hint": task.scenario_hint if task else None,
            "priority": task.priority if task else None,
            "risk_level": task.risk_level if task else None,
            "requires_approval": task.requires_approval if task else False,
            "owner_team": task.owner_team if task else None,
            "tags": task.tags if task else [],
        },
        "run": {
            "id": str(run.id),
            "scenario": run.scenario,
            "status": run.status,
            "failure_type": run.failure_type,
            "recovery_action": run.recovery_action,
            "confidence": run.confidence,
            "reliability_score": run.reliability_score,
            "selected_tool": run.selected_tool,
            "final_answer": run.final_answer,
            "run_profile": run.run_profile,
            "risk_level": run.risk_level,
            "graph_node_count": run.graph_node_count,
            "cost_units": run.cost_units,
            "approval_policy_fit": approval_policy_fit,
        },
        "trace_steps": [
            {
                "sequence": step.sequence,
                "stage": step.stage,
                "agent_name": step.agent_name,
                "tool_name": step.tool_name,
                "status": step.status,
                "input_snapshot": step.input_snapshot,
                "output_snapshot": step.output_snapshot,
                "confidence": step.confidence,
                "latency_ms": step.latency_ms,
                "metadata_json": step.metadata_json or {},
            }
            for step in trace_steps
        ],
        "selected_tool": selected_payload or {},
        "ranked_tools": ranked_tools,
    }
    return EvaluationContext(payload=payload)



def build_tool_decision_summary(
    *,
    selected_tool: str | None,
    selected_label: str | None,
    scenario: str,
    score: float,
    verdict: str,
) -> str:
    tool_name = selected_label or selected_tool or "no tool"
    if verdict == "ready":
        return f"{tool_name} is a defensible final tool for the {scenario} task. Decision audit score: {score:.2f}."
    return f"{tool_name} needs review for the {scenario} task. Decision audit score: {score:.2f}."


def build_tool_decision_checks(
    context: dict[str, Any],
    results: list[ScorerScoreResult],
) -> tuple[list[ToolDecisionCheck], list[str]]:
    run = context["run"]
    selected_tool = context.get("selected_tool", {}) or {}
    trace_steps = context.get("trace_steps", [])
    ranked_tools = context.get("ranked_tools", [])
    stages = {step.get("stage") for step in trace_steps}
    tool_names = [tool.get("name") for tool in ranked_tools]
    executor_step = next((step for step in trace_steps if step.get("stage") == "executor"), None)
    critic_step = next((step for step in trace_steps if step.get("stage") == "critic"), None)
    common_score = _average([result.score for result in results if result.level == "common"])
    scenario_score = _average([result.score for result in results if result.level == "scenario"])

    checks = [
        ToolDecisionCheck(
            name="Scenario-tool fit",
            score=1.0 if selected_tool.get("scenario_fit") else 0.0,
            passed=bool(selected_tool.get("scenario_fit")),
            signal=f"run.scenario={run['scenario']}; tool.scenario={selected_tool.get('scenario')}",
            explanation="The selected tool should match the routed scenario, or intentionally fall back to a general runtime tool.",
        ),
        ToolDecisionCheck(
            name="Candidate ranking",
            score=1.0 if run.get("selected_tool") and tool_names[:1] == [run.get("selected_tool")] else 0.65 if run.get("selected_tool") in tool_names[:3] else 0.0,
            passed=bool(run.get("selected_tool") in tool_names[:3]),
            signal=f"top_candidates={tool_names[:3]}",
            explanation="The final tool should be among the strongest candidates produced by the tool router.",
        ),
        ToolDecisionCheck(
            name="Risk and approval",
            score=1.0 if run.get("approval_policy_fit") else 0.0,
            passed=bool(run.get("approval_policy_fit")),
            signal=f"run.risk={run.get('risk_level')}; tool.risk={selected_tool.get('risk_level')}",
            explanation="High-risk tools or tasks must surface human approval, checkpoint, or recovery handling.",
        ),
        ToolDecisionCheck(
            name="Trace evidence",
            score=common_score,
            passed=common_score >= 0.75,
            signal=f"stages={sorted(stage for stage in stages if stage)}",
            explanation="A defensible tool decision needs visible router, planner, retrieval, tool router, executor, critic, and memory trace evidence.",
        ),
        ToolDecisionCheck(
            name="Execution outcome",
            score=1.0 if executor_step and run.get("status") != "failed" else 0.0,
            passed=bool(executor_step and run.get("status") != "failed"),
            signal=f"run.status={run.get('status')}; executor_present={bool(executor_step)}",
            explanation="The selected tool should produce an executor result rather than stopping at planning or routing.",
        ),
        ToolDecisionCheck(
            name="Critic validation",
            score=scenario_score if scenario_score else (1.0 if critic_step else 0.0),
            passed=bool(critic_step and (scenario_score == 0.0 or scenario_score >= 0.7)),
            signal=f"critic_present={bool(critic_step)}; scenario_score={scenario_score:.2f}",
            explanation="The critic should validate whether the selected tool and final result are grounded, safe, and complete for the scenario.",
        ),
    ]
    improvement_actions = [
        _improvement_for_check(check)
        for check in checks
        if not check.passed
    ]
    if not improvement_actions:
        improvement_actions.append("Keep the selected tool path; focus next on adding more labeled benchmark cases for this scenario.")
    return checks, improvement_actions


def _improvement_for_check(check: ToolDecisionCheck) -> str:
    actions = {
        "Scenario-tool fit": "Tighten scenario classification or add a scenario-specific tool constraint before ranking.",
        "Candidate ranking": "Expose more ranking features and verify the selected tool is actually the top candidate after scoring.",
        "Risk and approval": "Add or strengthen approval_gate handling for high-risk task or tool combinations.",
        "Trace evidence": "Persist the missing runtime stages so the tool decision can be audited end to end.",
        "Execution outcome": "Ensure the selected tool reaches executor output and records a structured result.",
        "Critic validation": "Require CriticAgent validation before accepting the final tool decision.",
    }
    return actions.get(check.name, "Review the failed decision signal and add a targeted scorer rule.")

class ScorerDslExecutor:
    def execute(self, definition: ScorerDefinitionPayload, context: dict[str, Any]) -> ScorerScoreResult:
        rule_results: list[ScorerRuleResult] = []
        total_weight = 0.0
        weighted_score = 0.0
        for rule in definition.rules:
            passed, actual = self._evaluate_rule(rule, context)
            score = 1.0 if passed else 0.0
            total_weight += rule.weight
            weighted_score += score * rule.weight
            rule_results.append(
                ScorerRuleResult(
                    id=rule.id,
                    passed=passed,
                    score=score,
                    reason=rule.reason,
                    actual=actual,
                    expected=rule.expected,
                    weight=rule.weight,
                )
            )
        final_score = round(weighted_score / total_weight, 2) if total_weight else 0.0
        threshold = definition.aggregation.pass_threshold
        return ScorerScoreResult(
            name=definition.name,
            level=definition.level,
            score=final_score,
            passed=final_score >= threshold,
            reason=f"Weighted score {final_score:.2f}, threshold {threshold:.2f}",
            rules=rule_results,
            definition=definition,
        )

    def _evaluate_rule(self, rule: ScorerRule, context: dict[str, Any]) -> tuple[bool, Any]:
        actual = _resolve(rule.source, rule.selector, context, expected=rule.expected)
        expected = rule.expected
        operator = rule.operator
        try:
            if operator == "exists":
                return _exists(actual), actual
            if operator == "not_exists":
                return not _exists(actual), actual
            if operator == "equals":
                return actual == expected, actual
            if operator == "not_equals":
                return actual != expected, actual
            if operator == "contains":
                expected_value = actual if expected is None else expected
                return _contains(actual, expected_value), actual
            if operator == "not_contains":
                expected_value = actual if expected is None else expected
                return not _contains(actual, expected_value), actual
            if operator == "gte":
                return float(actual or 0) >= float(expected or 0), actual
            if operator == "lte":
                return float(actual or 0) <= float(expected or 0), actual
            if operator == "in":
                return actual in (expected or []), actual
            if operator == "not_in":
                return actual not in (expected or []), actual
            if operator == "count_gte":
                return _count(actual) >= int(expected or 0), actual
            if operator == "count_lte":
                return _count(actual) <= int(expected or 0), actual
        except (TypeError, ValueError):
            return False, actual
        raise ValueError(f"Unsupported operator: {operator}")


def _resolve(source: str, selector: str, context: dict[str, Any], *, expected: Any = None) -> Any:
    if source == "trace_steps":
        return _resolve_trace(selector, context["trace_steps"])
    if source == "ranked_tools":
        values = [_get_path(item, selector) for item in context.get("ranked_tools", [])]
        return [value for value in values if value is not None]
    value = context.get(source, {})
    resolved = _get_path(value, selector)
    if selector == "name" and source == "selected_tool" and expected is None:
        return resolved
    return resolved


def _resolve_trace(selector: str, trace_steps: list[dict[str, Any]]) -> Any:
    if "." in selector:
        stage, field_path = selector.split(".", 1)
        matched = [step for step in trace_steps if step.get("stage") == stage]
        if len(matched) == 1:
            return _get_path(matched[0], field_path)
        return [_get_path(step, field_path) for step in matched]
    return [step.get(selector) for step in trace_steps]


def _get_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _contains(actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    if expected is None:
        return _exists(actual)
    if isinstance(actual, list):
        if isinstance(expected, list):
            return any(item in actual for item in expected)
        return expected in actual
    return str(expected).lower() in str(actual).lower()


def _exists(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return True


def _count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (list, dict, str)):
        return len(value)
    return 1


def _matches_scope(definition: ScorerDefinitionPayload, context: dict[str, Any]) -> bool:
    scope = definition.applies_to
    run = context["run"]
    task = context["task"]
    if scope.scenarios and run["scenario"] not in scope.scenarios:
        return False
    if scope.risk_levels and run["risk_level"] not in scope.risk_levels and task["risk_level"] not in scope.risk_levels:
        return False
    if scope.domain_tags:
        tags = set(task.get("tags") or [])
        if not tags.intersection(scope.domain_tags):
            return False
    return True


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


