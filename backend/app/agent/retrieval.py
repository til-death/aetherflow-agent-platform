from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import AgentScenario


@dataclass(frozen=True)
class KnowledgeArticle:
    key: str
    scenario: str
    title: str
    summary: str
    sections: tuple[str, ...]
    entities: tuple[str, ...]
    keywords: tuple[str, ...]


KNOWLEDGE: tuple[KnowledgeArticle, ...] = (
    KnowledgeArticle(
        key="agent_reliability_policy",
        scenario=AgentScenario.GENERAL,
        title="Agent reliability operating policy",
        summary="All automated runs must expose plan, evidence, tool choice, recovery action, and critic decision.",
        sections=(
            "Every run should be replayable through ordered trace events with inputs, outputs, latency, and confidence.",
            "High-risk actions require approval gates instead of direct external execution.",
            "A failed retrieval, tool call, or low-confidence critic result should trigger recovery or human checkpoint.",
        ),
        entities=("trace", "critic", "recovery", "approval"),
        keywords=("reliability", "trace", "critic", "recovery", "approval", "agent"),
    ),
    KnowledgeArticle(
        key="enterprise_onboarding_runbook",
        scenario=AgentScenario.WORKFLOW,
        title="Enterprise onboarding runbook",
        summary="Enterprise onboarding tasks require owner mapping, dependency checks, SLA checkpoint, and handoff notes.",
        sections=(
            "Identify customer owner, internal team owner, blocked dependency, and promised completion date.",
            "If SLA is near breach, route to workflow escalation and create an explicit next checkpoint.",
            "If finance or security approval is missing, keep execution in needs_approval state.",
        ),
        entities=("customer owner", "security approval", "SLA", "handoff"),
        keywords=("onboarding", "handoff", "sla", "approval", "owner", "workflow"),
    ),
    KnowledgeArticle(
        key="incident_dependency_graph",
        scenario=AgentScenario.KNOWLEDGE,
        title="Project dependency graph playbook",
        summary="Root-cause tasks should expand project dependencies before concluding why a workflow failed.",
        sections=(
            "Map the named project to upstream services, owning teams, recent incidents, and pending approvals.",
            "Prefer multi-hop explanation over a single retrieved paragraph when dependencies are involved.",
            "Return evidence nodes and missing links separately so the operator can audit the reasoning path.",
        ),
        entities=("project", "dependency", "service", "incident", "owner"),
        keywords=("why", "failed", "dependency", "incident", "owner", "root cause"),
    ),
    KnowledgeArticle(
        key="data_anomaly_playbook",
        scenario=AgentScenario.ANALYSIS,
        title="Metric anomaly analysis playbook",
        summary="Data analysis tasks should separate data quality checks, cohort comparison, and action recommendation.",
        sections=(
            "Check schema, missing values, outliers, and time window before making business conclusions.",
            "Compare affected segment against baseline and label likely causes as data issue, product issue, or external factor.",
            "Generate next experiment or owner handoff only after evidence reaches confidence threshold.",
        ),
        entities=("schema", "outlier", "cohort", "baseline", "owner"),
        keywords=("analysis", "anomaly", "metric", "csv", "revenue", "cohort", "dashboard"),
    ),
    KnowledgeArticle(
        key="sandbox_execution_policy",
        scenario=AgentScenario.CODE,
        title="Sandbox execution policy",
        summary="Code execution must be isolated, deterministic, time-limited, and observable.",
        sections=(
            "Use allowlisted libraries and block filesystem or network access unless the task explicitly requires it.",
            "Capture stdout, stderr, execution duration, and resource usage for trace replay.",
            "Never execute generated code directly against production systems; produce a patch or dry-run result first.",
        ),
        entities=("sandbox", "timeout", "stdout", "dry-run"),
        keywords=("python", "script", "code", "execute", "sandbox", "timeout", "dry-run"),
    ),
    KnowledgeArticle(
        key="external_api_governance",
        scenario=AgentScenario.EXTERNAL_API,
        title="External API action governance",
        summary="External actions need schema validation, idempotency keys, scoped credentials, and approval for high-risk writes.",
        sections=(
            "Rank tools by scenario match, semantic relevance, historical success, risk, and latency.",
            "For CRM, billing, finance, or customer-visible updates, create an approval checkpoint before final mutation.",
            "Record request schema, target system, and rollback plan in the trace metadata.",
        ),
        entities=("schema", "idempotency", "CRM", "rollback", "approval"),
        keywords=("api", "crm", "external", "webhook", "notify", "update", "idempotency"),
    ),
)


def progressive_retrieve(text: str, scenario: str) -> dict[str, Any]:
    candidates = []
    for article in KNOWLEDGE:
        overlap = sum(1 for keyword in article.keywords if keyword in text)
        scenario_bonus = 2 if article.scenario in {scenario, AgentScenario.GENERAL} else 0
        score = overlap + scenario_bonus
        if score:
            candidates.append((score, article))
    candidates.sort(key=lambda item: item[0], reverse=True)
    if not candidates:
        return {
            "score": 0.24,
            "brief": "No strong enterprise knowledge evidence found.",
            "documents": [],
            "sections": [],
            "chunks": [],
            "entities": [],
        }
    top = candidates[0][1]
    score = min(0.96, 0.44 + candidates[0][0] * 0.075)
    return {
        "score": round(score, 2),
        "brief": f"{top.title}: {top.summary}",
        "documents": [article.title for _, article in candidates[:3]],
        "sections": list(top.sections[:2]),
        "chunks": list(top.sections),
        "entities": list(top.entities),
        "retrieval_levels": ["document", "section", "chunk", "entity"],
    }


def recover_evidence(evidence: dict[str, Any], scenario: str) -> dict[str, Any]:
    fallback = next(article for article in KNOWLEDGE if article.key == "agent_reliability_policy")
    return {
        **evidence,
        "score": 0.48,
        "brief": f"Fallback evidence: {fallback.summary}",
        "documents": [fallback.title],
        "sections": list(fallback.sections[:2]),
        "chunks": list(fallback.sections),
        "entities": list(fallback.entities),
        "recovered": True,
        "scenario": scenario,
    }
