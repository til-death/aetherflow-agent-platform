from __future__ import annotations

import json
from typing import Any

from app.agent.llm import LLMClient, LLMError
from app.agent.retrieval import KNOWLEDGE
from app.agent.schemas import ExecutionGraphPlan
from app.agent.tool_registry import TOOLS
from app.agent.validators import (
    AgentValidationError,
    plan_to_graph,
    validate_execution_plan,
)
from app.models import AgentScenario, WorkflowTask


def build_execution_graph(
    *,
    llm: LLMClient,
    scenario: str,
    task: WorkflowTask | Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if llm.enabled:
        try:
            system = (
                "You are the Planner Agent inside AetherFlow, an enterprise agent runtime. "
                "Return an executable DAG only. Do not execute tools. Use only the supplied tools and scenarios. "
                "High-risk, code execution, external API, finance, production, or customer-visible work must include an approval gate."
            )
            user = json.dumps(
                {
                    "task": {
                        "title": task.title,
                        "objective": task.objective,
                        "context": task.context,
                        "expected_output": task.expected_output,
                        "scenario_hint": task.scenario_hint,
                        "priority": task.priority,
                        "risk_level": task.risk_level,
                        "requires_approval": task.requires_approval,
                        "tags": task.tags,
                    },
                    "routed_scenario": scenario,
                    "available_tools": [
                        {
                            "name": tool.name,
                            "scenario": tool.scenario,
                            "risk_level": tool.risk_level,
                            "description": tool.description,
                        }
                        for tool in TOOLS
                    ],
                    "knowledge_index": [
                        {
                            "title": article.title,
                            "scenario": article.scenario,
                            "entities": article.entities,
                            "summary": article.summary,
                        }
                        for article in KNOWLEDGE
                    ],
                    "required_runtime_stages": [
                        "normalize task",
                        "retrieve evidence",
                        "select or prepare tool",
                        "execute or dry-run",
                        "critic validation",
                        "memory policy",
                    ],
                },
                ensure_ascii=False,
            )
            plan = llm.complete_json(
                purpose="aetherflow_execution_graph_plan",
                system=system,
                user=user,
                schema_model=ExecutionGraphPlan,
            )
            validate_execution_plan(plan, allowed_tool_names={tool.name for tool in TOOLS})
            return plan_to_graph(plan), {
                "planner_mode": "llm_structured",
                "objective_summary": plan.objective_summary,
                "assumptions": plan.assumptions,
                "missing_context": plan.missing_context,
                "estimated_risk": plan.estimated_risk,
            }
        except (LLMError, AgentValidationError) as exc:
            graph = rule_execution_graph(scenario)
            return graph, {
                "planner_mode": "deterministic_fallback",
                "fallback_reason": _clip(str(exc), 500),
                "llm_enabled": True,
            }

    return rule_execution_graph(scenario), {
        "planner_mode": "deterministic_rule",
        "llm_enabled": False,
    }


def rule_execution_graph(scenario: str) -> list[dict[str, Any]]:
    graph = [
        {"id": "normalize_task", "agent": "PlannerAgent", "depends_on": [], "output_type": "task_contract"},
        {
            "id": "route_scenario",
            "agent": "ScenarioRouter",
            "depends_on": ["normalize_task"],
            "output_type": "scenario",
        },
        {
            "id": "retrieve_evidence",
            "agent": "RAGAgent",
            "depends_on": ["route_scenario"],
            "output_type": "evidence_bundle",
        },
    ]
    scenario_nodes = {
        AgentScenario.KNOWLEDGE: [
            ("expand_graph_neighbors", "RAGAgent", "entity_path"),
            ("synthesize_grounded_answer", "ExecutorAgent", "answer"),
        ],
        AgentScenario.WORKFLOW: [
            ("check_process_state", "ExecutorAgent", "state_diff"),
            ("approval_gate", "CriticAgent", "approval_checkpoint"),
            ("build_handoff_plan", "ExecutorAgent", "workflow_action"),
        ],
        AgentScenario.CODE: [
            ("prepare_sandbox_plan", "ExecutorAgent", "sandbox_spec"),
            ("approval_gate", "CriticAgent", "approval_checkpoint"),
            ("dry_run_code", "ExecutorAgent", "execution_report"),
        ],
        AgentScenario.ANALYSIS: [
            ("profile_dataset", "ExecutorAgent", "data_profile"),
            ("explain_metric_shift", "CriticAgent", "analysis_report"),
        ],
        AgentScenario.EXTERNAL_API: [
            ("validate_api_schema", "ExecutorAgent", "api_contract"),
            ("approval_gate", "CriticAgent", "approval_checkpoint"),
            ("prepare_idempotent_action", "ExecutorAgent", "action_plan"),
        ],
        AgentScenario.GENERAL: [
            ("summarize_request", "ExecutorAgent", "summary"),
            ("ask_missing_context", "CriticAgent", "question_set"),
        ],
    }
    depends_on = "retrieve_evidence"
    for node_id, agent, output_type in scenario_nodes.get(scenario, scenario_nodes[AgentScenario.GENERAL]):
        graph.append({"id": node_id, "agent": agent, "depends_on": [depends_on], "output_type": output_type})
        depends_on = node_id
    graph.append(
        {"id": "critic_validate", "agent": "CriticAgent", "depends_on": [depends_on], "output_type": "validation_decision"}
    )
    graph.append(
        {"id": "memory_policy", "agent": "MemoryAgent", "depends_on": ["critic_validate"], "output_type": "memory_decision"}
    )
    return graph


def _clip(value: str | None, limit: int = 900) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else value[: limit - 3] + "..."
