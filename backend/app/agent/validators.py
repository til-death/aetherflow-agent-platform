from __future__ import annotations

from app.agent.schemas import CriticDecision, ExecutionGraphPlan


class AgentValidationError(ValueError):
    pass


def validate_execution_plan(plan: ExecutionGraphPlan, *, allowed_tool_names: set[str]) -> None:
    ids = [node.id for node in plan.nodes]
    if len(ids) != len(set(ids)):
        raise AgentValidationError("Planner returned duplicate DAG node ids")

    id_set = set(ids)
    for node in plan.nodes:
        missing_dependencies = [dep for dep in node.depends_on if dep not in id_set]
        if missing_dependencies:
            raise AgentValidationError(f"Node {node.id} depends on unknown nodes: {missing_dependencies}")
        unknown_tools = [tool for tool in node.allowed_tools if tool not in allowed_tool_names]
        if unknown_tools:
            raise AgentValidationError(f"Node {node.id} references unregistered tools: {unknown_tools}")

    _assert_acyclic(plan)

    agents = {node.agent for node in plan.nodes}
    required_agents = {"PlannerAgent", "ExecutorAgent", "CriticAgent"}
    missing_agents = required_agents - agents
    if missing_agents:
        raise AgentValidationError(f"Planner DAG missing required agents: {sorted(missing_agents)}")

    if not any(node.agent == "RAGAgent" for node in plan.nodes):
        raise AgentValidationError("Planner DAG must include an evidence retrieval node")

    has_high_risk_node = any(node.risk_level == "high" for node in plan.nodes)
    has_external_action = any(node.scenario == "external_api" for node in plan.nodes)
    has_approval_gate = any("approval_gate" in node.allowed_tools or "approval" in node.id for node in plan.nodes)
    if (has_high_risk_node or has_external_action) and not has_approval_gate:
        raise AgentValidationError("High-risk or external API DAG must include an approval gate")


def plan_to_graph(plan: ExecutionGraphPlan) -> list[dict[str, object]]:
    return [
        {
            "id": node.id,
            "description": node.description,
            "agent": node.agent,
            "scenario": node.scenario,
            "depends_on": node.depends_on,
            "output_type": node.expected_output_type,
            "risk_level": node.risk_level,
            "allowed_tools": node.allowed_tools,
        }
        for node in plan.nodes
    ]


def validate_critic_decision(
    decision: CriticDecision,
    *,
    selected_tool: dict[str, object],
    scenario: str,
    evidence_score: float,
) -> None:
    if evidence_score < 0.5 and decision.decision == "runtime_execution_ready":
        raise AgentValidationError("Critic allowed execution despite weak evidence")
    if decision.evidence_coverage < 0.45 and decision.decision == "runtime_execution_ready":
        raise AgentValidationError("Critic allowed execution despite low evidence coverage")
    if decision.hallucination_risk > 0.55 and not decision.needs_approval:
        raise AgentValidationError("Critic did not gate high hallucination risk")
    if scenario == "external_api" and not decision.needs_approval:
        raise AgentValidationError("External API scenario must require approval")
    if selected_tool.get("risk_level") == "high" and not decision.needs_approval:
        raise AgentValidationError("High-risk selected tool must require approval")


def _assert_acyclic(plan: ExecutionGraphPlan) -> None:
    deps = {node.id: set(node.depends_on) for node in plan.nodes}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise AgentValidationError("Planner DAG contains a cycle")
        visiting.add(node_id)
        for dep in deps[node_id]:
            visit(dep)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in deps:
        visit(node_id)
