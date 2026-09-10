from __future__ import annotations

import json
from typing import Any

from app.agent.llm import LLMClient, LLMError
from app.agent.schemas import CriticDecision
from app.agent.validators import AgentValidationError, validate_critic_decision
from app.models import AgentScenario, WorkflowRiskLevel, WorkflowTask


def critic_review(
    *,
    llm: LLMClient,
    task: WorkflowTask | Any,
    scenario: str,
    graph: list[dict[str, Any]],
    evidence: dict[str, Any],
    selected_tool: dict[str, Any],
    tool_result: dict[str, Any],
    task_text: str,
) -> dict[str, Any]:
    if llm.enabled:
        try:
            system = (
                "You are the Critic Agent inside AetherFlow. Validate whether the planned and executed result "
                "is grounded, safe, and complete. Check evidence coverage, tool-risk fit, approval need, missing context, "
                "and hallucination risk. Return a structured decision only."
            )
            user = json.dumps(
                {
                    "task": {
                        "title": task.title,
                        "objective": task.objective,
                        "context": task.context,
                        "expected_output": task.expected_output,
                        "priority": task.priority,
                        "risk_level": task.risk_level,
                        "requires_approval": task.requires_approval,
                        "tags": task.tags,
                    },
                    "scenario": scenario,
                    "execution_graph": graph,
                    "evidence": evidence,
                    "selected_tool": selected_tool,
                    "tool_result": tool_result,
                    "runtime_policy": {
                        "external_api_requires_approval": True,
                        "high_risk_tool_requires_approval": True,
                        "weak_evidence_threshold": 0.5,
                    },
                },
                ensure_ascii=False,
            )
            decision = llm.complete_json(
                purpose="aetherflow_critic_decision",
                system=system,
                user=user,
                schema_model=CriticDecision,
            )
            validate_critic_decision(
                decision,
                selected_tool=selected_tool,
                scenario=scenario,
                evidence_score=float(evidence["score"]),
            )
            needs_approval = decision.needs_approval or decision.decision != "runtime_execution_ready"
            return {
                "decision": decision.decision,
                "needs_approval": needs_approval,
                "blockers": decision.blockers,
                "risk_level": decision.risk_level,
                "confidence": round(decision.confidence, 2),
                "evidence_coverage": round(decision.evidence_coverage, 2),
                "hallucination_risk": round(decision.hallucination_risk, 2),
                "recommended_recovery": decision.recommended_recovery,
                "critic_mode": "llm_structured",
            }
        except (LLMError, AgentValidationError) as exc:
            critique = rule_critic_review(task, scenario, evidence, selected_tool, tool_result, task_text)
            critique.update(
                {
                    "critic_mode": "deterministic_fallback",
                    "fallback_reason": _clip(str(exc), 500),
                    "llm_enabled": True,
                }
            )
            return critique

    critique = rule_critic_review(task, scenario, evidence, selected_tool, tool_result, task_text)
    critique.update({"critic_mode": "deterministic_rule", "llm_enabled": False})
    return critique


def rule_critic_review(
    task: WorkflowTask | Any,
    scenario: str,
    evidence: dict[str, Any],
    selected_tool: dict[str, Any],
    tool_result: dict[str, Any],
    task_text: str,
) -> dict[str, Any]:
    high_risk_terms = (
        "legal",
        "finance",
        "billing",
        "production",
        "delete",
        "customer-visible",
        "credential",
        "critical",
        "contract",
    )
    risk_text = task_text
    for negated_phrase in (
        "no production",
        "without production",
        "not production",
        "no customer-visible",
        "without customer-visible",
        "not customer-visible",
    ):
        risk_text = risk_text.replace(negated_phrase, "")
    # A memory task may quote risky policies as content to be remembered. That
    # mention alone is not an external mutation, so it must not create a false
    # approval block for the memory-writing policy.
    high_risk = (
        selected_tool["risk_level"] == WorkflowRiskLevel.HIGH
        or (scenario != AgentScenario.GENERAL and any(term in risk_text for term in high_risk_terms))
    )
    low_evidence = evidence["score"] < 0.5
    missing_expected_output = tool_result.get("expected_output_missing", False)
    needs_approval = task.requires_approval or high_risk or low_evidence or scenario == AgentScenario.EXTERNAL_API
    confidence = 0.91
    if needs_approval:
        confidence -= 0.15
    if low_evidence:
        confidence -= 0.11
    if missing_expected_output:
        confidence -= 0.06
    blockers = []
    if high_risk:
        blockers.append("high_risk_action")
    if low_evidence:
        blockers.append("weak_evidence")
    if missing_expected_output:
        blockers.append("missing_expected_output")
    risk_level = WorkflowRiskLevel.HIGH if high_risk else WorkflowRiskLevel.MEDIUM if low_evidence else task.risk_level
    return {
        "decision": "approval_checkpoint_required" if needs_approval else "runtime_execution_ready",
        "needs_approval": needs_approval,
        "blockers": blockers,
        "risk_level": risk_level,
        "confidence": round(max(0.45, confidence), 2),
        "evidence_coverage": float(evidence["score"]),
        "hallucination_risk": 0.24 if not low_evidence else 0.58,
        "recommended_recovery": "approval_gate" if needs_approval else None,
    }


def _clip(value: str | None, limit: int = 900) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else value[: limit - 3] + "..."

