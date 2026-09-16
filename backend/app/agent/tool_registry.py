from __future__ import annotations

import math
import re
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
    # Capability cues describe the tool's decision boundary rather than its
    # broad topic. They are used only in the second-stage reranker.
    capability_cues: tuple[str, ...] = ()
    exclusion_cues: tuple[str, ...] = ()


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
        capability_cues=("policy", "制度", "政策", "runbook", "手册", "原文依据", "证据来源", "citation"),
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
        capability_cues=("dependency graph", "依赖拓扑", "上下游", "影响面", "责任链", "多跳关系", "owner mapping", "关系图"),
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
        capability_cues=("state transition", "状态流转", "流程状态", "handoff", "交接", "controlled state", "推进节点"),
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
        capability_cues=("approval gate", "人工确认", "等待审批", "审批点", "高风险", "human checkpoint", "人工复核", "拦截执行"),
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
        capability_cues=("python sandbox", "受限环境", "隔离环境", "sandbox", "timeout", "memory budget", "stdout", "资源限制"),
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
        capability_cues=("data profiling", "字段画像", "结构化画像", "field profile", "异常候选", "schema quality", "数据质量", "缺失值"),
    ),
    ToolDefinition(
        name="http_api_connector",
        label="HTTP API connector",
        scenario=AgentScenario.EXTERNAL_API,
        risk_level=WorkflowRiskLevel.HIGH,
        avg_latency_ms=290,
        success_rate=0.8,
        keywords=(
            "http",
            "api",
            "crm",
            "work item",
            "external",
            "webhook",
            "notify",
            "update",
            "schema",
            "validate",
            "validation",
            "idempotent",
            "idempotency",
            "接口",
            "外部系统",
            "第三方",
            "同步",
            "批量",
            "写入",
            "更新",
            "回调",
            "通知",
            "参数",
            "校验",
            "幂等",
            "方案",
        ),
        description="Calls approved external APIs through schema validation and idempotency checks.",
        capability_cues=("schema validation", "幂等键", "idempotency key", "dry-run", "回滚方案", "scoped credential", "外部接口", "参数校验"),
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
        capability_cues=("long-term memory", "长期记忆", "短期记忆", "用户偏好", "memory policy", "记忆策略"),
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
    normalized_keywords = tuple(str(keyword).lower() for keyword in raw.get("keywords", []))
    raw_capability_cues = raw.get("capability_cues")
    capability_cues = (
        tuple(str(cue).lower() for cue in raw_capability_cues)
        if raw_capability_cues
        else normalized_keywords
    )
    return ToolDefinition(
        name=str(raw["name"]),
        label=str(raw.get("label") or raw["name"]),
        scenario=str(raw.get("scenario") or AgentScenario.GENERAL),
        risk_level=str(raw.get("risk_level") or WorkflowRiskLevel.MEDIUM),
        avg_latency_ms=int(raw.get("avg_latency_ms") or 260),
        success_rate=float(raw.get("success_rate") or 0.75),
        keywords=normalized_keywords,
        description=str(raw.get("description") or "Dynamic tool loaded from benchmark tool library."),
        capability_cues=capability_cues,
        exclusion_cues=tuple(str(cue).lower() for cue in raw.get("exclusion_cues", [])),
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
    available_tools = tuple(tools)
    keyword_document_frequency = {
        keyword: sum(1 for tool in available_tools if keyword in tool.keywords)
        for tool in available_tools
        for keyword in tool.keywords
    }
    capability_document_frequency = {
        cue: sum(1 for tool in available_tools if cue in tool.capability_cues)
        for tool in available_tools
        for cue in tool.capability_cues
    }
    ranked = []
    for tool in available_tools:
        scenario_match = 1.0 if tool.scenario == scenario else 0.36 if tool.scenario == AgentScenario.GENERAL else 0.08
        matches = [keyword for keyword in tool.keywords if keyword and keyword in text]
        capability_matches = [cue for cue in tool.capability_cues if cue and cue in text]
        exclusion_matches = [cue for cue in tool.exclusion_cues if cue and cue in text]
        match_count = len(matches)
        weighted_matches = sum(
            1.0 + math.log((len(available_tools) + 1) / (keyword_document_frequency.get(keyword, 0) + 1))
            for keyword in matches
        )
        total_keyword_weight = sum(
            1.0 + math.log((len(available_tools) + 1) / (keyword_document_frequency.get(keyword, 0) + 1))
            for keyword in tool.keywords
        )
        # Use an absolute evidence floor so short generic descriptions cannot
        # win merely because they contain fewer keywords than a specialist.
        semantic = min(1.0, weighted_matches / max(5.0, total_keyword_weight * 0.34))
        name_tokens = [token for token in re.split(r"[_\-\s]+", tool.name.lower()) if len(token) > 2]
        name_match_bonus = min(0.1, sum(0.035 for token in name_tokens if token in text))
        specificity_bonus = min(0.14, match_count * 0.02) + name_match_bonus
        # A broad keyword hit gets a candidate into Top-K; distinctive
        # capability cues decide between otherwise similar tools.
        capability_weight = sum(
            1.0 + math.log((len(available_tools) + 1) / (capability_document_frequency.get(cue, 0) + 1))
            for cue in capability_matches
        )
        capability_bonus = min(0.22, capability_weight * 0.055)
        boundary_penalty = min(0.16, len(exclusion_matches) * 0.05)
        risk_penalty = {WorkflowRiskLevel.LOW: 0.02, WorkflowRiskLevel.MEDIUM: 0.06, WorkflowRiskLevel.HIGH: 0.12}.get(
            tool.risk_level,
            0.06,
        )
        latency_penalty = min(0.12, tool.avg_latency_ms / 3200)
        dynamic_boost = 0.035 if tool.name.startswith("toolluban_") else 0.0
        score = scenario_match * 0.34 + semantic * 0.34 + tool.success_rate * 0.18 + specificity_bonus + capability_bonus + dynamic_boost - boundary_penalty - risk_penalty - latency_penalty
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
                "capability_matches": capability_matches,
                "exclusion_matches": exclusion_matches,
            }
        )
    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def assess_tool_decision(
    text: str,
    scenario: str,
    ranked_tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply a conservative execution policy after candidate reranking.

    Ranking answers "which tool is the best candidate?". This policy answers
    the separate operational question "is the evidence strong enough to run
    it?". Thresholds are intentionally fixed and explainable so selective
    evaluation measures behavior rather than tuning a particular holdout.
    """
    if not ranked_tools:
        return {
            "decision": "abstain",
            "reason": "no_candidate_tool",
            "reasons": ["no_candidate_tool"],
            "confidence": 0.0,
            "margin": 0.0,
            "preconditions_ok": False,
        }

    top1 = ranked_tools[0]
    top2 = ranked_tools[1] if len(ranked_tools) > 1 else None
    score = float(top1.get("score", 0.0))
    margin = round(score - float(top2.get("score", 0.0)), 4) if top2 else score
    reasons: list[str] = []
    normalized_text = text.lower()

    if score < 0.58:
        reasons.append("low_top1_score")
    # A small margin is concerning when absolute evidence is weak. Once the
    # top candidate has strong evidence, close scores often represent two
    # valid variants of the same capability and should not trigger needless
    # abstention.
    if top2 and margin < 0.04 and score < 0.9:
        reasons.append("small_top1_margin")
    if top1.get("exclusion_matches"):
        reasons.append("tool_boundary_conflict")
    if top1.get("scenario") not in {scenario, "general"}:
        reasons.append("scenario_tool_mismatch")

    precondition_markers = {
        "analysis": ("csv", "table", "spreadsheet", "数据", "表格", "文件", "export", "extract"),
        "code": ("python", "script", "code", "sandbox", "代码", "脚本", "程序", "执行"),
        "external_api": ("api", "http", "webhook", "external", "endpoint", "接口", "第三方", "同步", "partner"),
    }
    required_markers = precondition_markers.get(scenario)
    if required_markers and not any(marker in normalized_text for marker in required_markers):
        reasons.append("missing_scenario_input")

    return {
        "decision": "abstain" if reasons else "execute",
        "reason": reasons[0] if reasons else "ready",
        "reasons": reasons,
        "confidence": round(max(0.0, min(1.0, score + min(0.12, max(0.0, margin)))), 2),
        "margin": round(margin, 2),
        "preconditions_ok": "missing_scenario_input" not in reasons,
    }


