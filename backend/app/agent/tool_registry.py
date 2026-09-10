from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.models import (
    AgentScenario,
    ToolDefinitionPublic,
    WorkflowRiskLevel,
    WorkflowTask,
)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    label: str
    scenario: str
    risk_level: str
    avg_latency_ms: int
    success_rate: float
    keywords: tuple[str, ...]
    description: str


TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="hybrid_knowledge_search",
        label="Hybrid knowledge search",
        scenario=AgentScenario.KNOWLEDGE,
        risk_level=WorkflowRiskLevel.LOW,
        avg_latency_ms=210,
        success_rate=0.9,
        keywords=("policy", "document", "knowledge", "runbook", "dependency", "why", "知识", "文档", "制度", "手册", "依赖", "原因", "根因"),
        description="Retrieves policy, runbook, and graph-neighbor evidence before answer synthesis.",
    ),
    ToolDefinition(
        name="graph_neighbor_expand",
        label="Graph neighbor expansion",
        scenario=AgentScenario.KNOWLEDGE,
        risk_level=WorkflowRiskLevel.LOW,
        avg_latency_ms=260,
        success_rate=0.86,
        keywords=("dependency", "owner", "incident", "root cause", "relationship", "依赖", "负责人", "事故", "根因", "关系", "链路", "影响面"),
        description="Expands entities through project, service, owner, and incident relationships.",
    ),
    ToolDefinition(
        name="workflow_state_transition",
        label="Workflow state transition",
        scenario=AgentScenario.WORKFLOW,
        risk_level=WorkflowRiskLevel.MEDIUM,
        avg_latency_ms=240,
        success_rate=0.88,
        keywords=("approve", "handoff", "sla", "workflow", "owner", "process", "流程", "流转", "交接", "负责人", "节点", "状态", "推进", "派发"),
        description="Moves a business workflow to the next controlled state with audit metadata.",
    ),
    ToolDefinition(
        name="approval_gate",
        label="Approval gate",
        scenario=AgentScenario.WORKFLOW,
        risk_level=WorkflowRiskLevel.HIGH,
        avg_latency_ms=180,
        success_rate=0.93,
        keywords=("approval", "risk", "legal", "finance", "critical", "human", "审批", "人工", "高风险", "财务", "法务", "合规", "确认", "拦截"),
        description="Blocks high-risk actions and creates a human checkpoint before execution.",
    ),
    ToolDefinition(
        name="python_sandbox_runner",
        label="Python sandbox runner",
        scenario=AgentScenario.CODE,
        risk_level=WorkflowRiskLevel.HIGH,
        avg_latency_ms=360,
        success_rate=0.82,
        keywords=("python", "script", "code", "execute", "reconcile", "calculate", "代码", "脚本", "执行", "计算", "沙箱", "核对", "对账"),
        description="Runs constrained Python snippets with timeout, memory budget, and captured stdout.",
    ),
    ToolDefinition(
        name="data_frame_profiler",
        label="Data frame profiler",
        scenario=AgentScenario.ANALYSIS,
        risk_level=WorkflowRiskLevel.MEDIUM,
        avg_latency_ms=310,
        success_rate=0.85,
        keywords=("csv", "metric", "analysis", "anomaly", "dashboard", "cohort", "revenue", "missing", "数据", "指标", "分析", "异常", "画像", "缺失", "收入", "报表", "字段"),
        description="Profiles tabular data, flags anomalies, and returns a structured analysis summary.",
    ),
    ToolDefinition(
        name="http_api_connector",
        label="HTTP API connector",
        scenario=AgentScenario.EXTERNAL_API,
        risk_level=WorkflowRiskLevel.HIGH,
        avg_latency_ms=290,
        success_rate=0.8,
        keywords=("api", "crm", "work item", "external", "webhook", "notify", "update", "接口", "外部系统", "第三方", "同步", "批量", "写入", "更新", "回调", "通知"),
        description="Calls approved external APIs through schema validation and idempotency checks.",
    ),
    ToolDefinition(
        name="memory_write_policy",
        label="Memory write policy",
        scenario=AgentScenario.GENERAL,
        risk_level=WorkflowRiskLevel.LOW,
        avg_latency_ms=110,
        success_rate=0.92,
        keywords=("preference", "memory", "lesson", "summary", "insight", "偏好", "记忆", "经验", "总结", "沉淀", "长期", "短期"),
        description="Decides whether a run insight should be saved to short-term or long-term memory.",
    ),
)


SCENARIO_TEAM = {
    AgentScenario.KNOWLEDGE: "knowledge-platform",
    AgentScenario.WORKFLOW: "workflow-ops",
    AgentScenario.CODE: "automation-platform",
    AgentScenario.ANALYSIS: "data-ops",
    AgentScenario.EXTERNAL_API: "integration-ops",
    AgentScenario.GENERAL: "agent-runtime",
}


def normalize_tool(raw: dict[str, Any]) -> ToolDefinition:
    return ToolDefinition(
        name=str(raw["name"]),
        label=str(raw.get("label") or raw["name"]),
        scenario=str(raw.get("scenario") or AgentScenario.GENERAL),
        risk_level=str(raw.get("risk_level") or WorkflowRiskLevel.MEDIUM),
        avg_latency_ms=int(raw.get("avg_latency_ms") or 260),
        success_rate=float(raw.get("success_rate") or 0.75),
        keywords=tuple(str(keyword).lower() for keyword in raw.get("keywords", [])),
        description=str(raw.get("description") or "Dynamic tool loaded from benchmark tool library."),
    )


def list_tools(tools: Iterable[ToolDefinition] = TOOLS) -> list[ToolDefinitionPublic]:
    return [
        ToolDefinitionPublic(
            name=tool.name,
            label=tool.label,
            scenario=tool.scenario,
            risk_level=tool.risk_level,
            avg_latency_ms=tool.avg_latency_ms,
            success_rate=tool.success_rate,
            description=tool.description,
        )
        for tool in tools
    ]


def task_text(task: WorkflowTask | Any) -> str:
    parts = [
        task.title,
        task.objective,
        task.context or "",
        task.expected_output or "",
        task.scenario_hint or "",
        " ".join(task.tags or []),
    ]
    return " ".join(parts).lower()


def classify_scenario(task: WorkflowTask | Any, text: str, tools: Iterable[ToolDefinition] = TOOLS) -> tuple[str, float]:
    valid_hints = {
        AgentScenario.KNOWLEDGE,
        AgentScenario.WORKFLOW,
        AgentScenario.CODE,
        AgentScenario.ANALYSIS,
        AgentScenario.EXTERNAL_API,
        AgentScenario.GENERAL,
    }
    if task.scenario_hint in valid_hints and task.scenario_hint != AgentScenario.GENERAL:
        return task.scenario_hint, 0.88

    memory_terms = ("memory", "preference", "记忆", "偏好", "长期记忆", "短期记忆", "沉淀")
    if sum(1 for term in memory_terms if term in text) >= 2:
        return AgentScenario.GENERAL, 0.82

    available_tools = tuple(tools)
    # Keep tie-breaking stable across Python processes; a set here would make
    # equal-scoring scenarios depend on hash randomization.
    scenario_order = (
        AgentScenario.KNOWLEDGE,
        AgentScenario.WORKFLOW,
        AgentScenario.CODE,
        AgentScenario.ANALYSIS,
        AgentScenario.EXTERNAL_API,
    )
    scores: dict[str, float] = {}
    for scenario in scenario_order:
        tool_matches = [sum(1 for keyword in tool.keywords if keyword and keyword in text) for tool in available_tools if tool.scenario == scenario]
        if not tool_matches:
            scores[scenario] = 0.0
            continue
        scores[scenario] = max(tool_matches) + sum(tool_matches) * 0.12
    scenario, score = max(scores.items(), key=lambda item: item[1])
    if score == 0:
        return AgentScenario.GENERAL, 0.54
    return scenario, min(0.95, 0.58 + score * 0.06)


def scenario_action_space(scenario: str, tools: Iterable[ToolDefinition] = TOOLS) -> int:
    return sum(1 for tool in tools if tool.scenario in {scenario, AgentScenario.GENERAL})


def rank_tools(text: str, scenario: str, tools: Iterable[ToolDefinition] = TOOLS) -> list[dict[str, Any]]:
    ranked = []
    for tool in tools:
        scenario_match = 1.0 if tool.scenario == scenario else 0.36 if tool.scenario == AgentScenario.GENERAL else 0.08
        match_count = sum(1 for keyword in tool.keywords if keyword and keyword in text)
        semantic = min(1.0, match_count / max(2.5, len(tool.keywords) * 0.45))
        specificity_bonus = min(0.12, match_count * 0.015)
        risk_penalty = {WorkflowRiskLevel.LOW: 0.02, WorkflowRiskLevel.MEDIUM: 0.06, WorkflowRiskLevel.HIGH: 0.12}.get(
            tool.risk_level,
            0.06,
        )
        latency_penalty = min(0.12, tool.avg_latency_ms / 3200)
        dynamic_boost = 0.035 if tool.name.startswith("toolluban_") else 0.0
        score = scenario_match * 0.34 + semantic * 0.34 + tool.success_rate * 0.18 + specificity_bonus + dynamic_boost - risk_penalty - latency_penalty
        ranked.append(
            {
                "name": tool.name,
                "label": tool.label,
                "score": round(max(0.05, score), 2),
                "scenario": tool.scenario,
                "risk_level": tool.risk_level,
                "success_rate": tool.success_rate,
                "avg_latency_ms": tool.avg_latency_ms,
                "description": tool.description,
            }
        )
    return sorted(ranked, key=lambda item: item["score"], reverse=True)


