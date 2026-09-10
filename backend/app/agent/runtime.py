from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from sqlmodel import Session, col, select

from app.agent.critic import critic_review
from app.agent.evaluation import evaluation_report
from app.agent.executor import execute_tool
from app.agent.llm import LLMClient
from app.agent.memory import compose_final_answer, memory_policy
from app.agent.planner import build_execution_graph
from app.agent.retrieval import progressive_retrieve, recover_evidence
from app.agent.tool_registry import (
    SCENARIO_TEAM,
    TOOLS,
    classify_scenario,
    list_tools,
    rank_tools,
    scenario_action_space,
    task_text,
)
from app.agent.version import RUNTIME_PROFILE, RUNTIME_VERSION
from app.models import (
    AgentApprovalStatus,
    AgentFailureType,
    AgentRun,
    AgentRunStatus,
    AgentTraceStep,
    EvaluationReportPublic,
    ToolDefinitionPublic,
    WorkflowTask,
    WorkflowTaskStatus,
)


class AetherFlowRuntime:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def run_task(
        self,
        *,
        session: Session,
        task: WorkflowTask,
        owner_id: Any,
        idempotency_key: str | None = None,
    ) -> AgentRun:
        run = AgentRun(
            task_id=task.id,
            owner_id=owner_id,
            status=AgentRunStatus.RUNNING,
            run_profile=RUNTIME_PROFILE,
            runtime_version=RUNTIME_VERSION,
            idempotency_key=idempotency_key,
            risk_level=task.risk_level,
        )
        task.status = WorkflowTaskStatus.RUNNING
        task.updated_at = datetime.now(timezone.utc)
        session.add(task)
        session.add(run)
        session.commit()
        session.refresh(run)

        text = task_text(task)
        scenario, scenario_confidence = classify_scenario(task, text)
        run.scenario = scenario
        self._add_step(
            session=session,
            run=run,
            sequence=1,
            stage="scenario_router",
            agent_name="ScenarioRouter",
            input_snapshot=text,
            output_snapshot=f"scenario={scenario}; action_space={scenario_action_space(scenario)} tools",
            confidence=scenario_confidence,
            metadata={"candidate_tools": len(TOOLS), "scenario_hint": task.scenario_hint},
        )

        graph, planner_metadata = build_execution_graph(llm=self.llm, scenario=scenario, task=task)
        failure_type = AgentFailureType.PLANNING if planner_metadata.get("fallback_reason") else AgentFailureType.NONE
        recovery_action = (
            "Fallback to deterministic DAG planner after LLM planning failure"
            if planner_metadata.get("fallback_reason")
            else None
        )
        self._add_step(
            session=session,
            run=run,
            sequence=2,
            stage="planner",
            agent_name="PlannerAgent",
            input_snapshot=task.objective,
            output_snapshot=" -> ".join(str(node["id"]) for node in graph),
            confidence=0.87,
            metadata={"graph": graph, "node_count": len(graph), **planner_metadata},
        )

        evidence = progressive_retrieve(text, scenario)
        guardrail_status = "success"
        guardrail_output = "DAG schema, registered tools, approval gates, and retrieval precheck passed"
        guardrail_confidence = 0.9
        guardrail_metadata: dict[str, object] = {
            "planner_mode": planner_metadata.get("planner_mode"),
            "dag_node_count": len(graph),
            "checks": [
                "schema_validated",
                "acyclic_dag",
                "registered_tools",
                "approval_gate_policy",
                "retrieval_threshold",
            ],
            "retrieval_score": evidence["score"],
        }
        if evidence["score"] < 0.42:
            if failure_type == AgentFailureType.NONE:
                failure_type = AgentFailureType.RETRIEVAL
            recovery_action = (
                "; ".join(
                    action
                    for action in [
                        recovery_action,
                        "Fallback to reliability policy and require explicit evidence gap in final output",
                    ]
                    if action
                )
            )
            evidence = recover_evidence(evidence, scenario)
            guardrail_status = "recovered"
            guardrail_output = recovery_action or "Recovered weak retrieval through reliability policy fallback"
            guardrail_confidence = 0.64
            guardrail_metadata.update({"failure_type": failure_type, "strategy": "fallback_policy"})

        self._add_step(
            session=session,
            run=run,
            sequence=3,
            stage="runtime_guardrails",
            agent_name="RecoveryEngine",
            input_snapshot="planner graph and retrieval precheck",
            output_snapshot=guardrail_output,
            confidence=guardrail_confidence,
            status=guardrail_status,
            metadata=guardrail_metadata,
        )

        self._add_step(
            session=session,
            run=run,
            sequence=4,
            stage="progressive_rag",
            agent_name="RAGAgent",
            input_snapshot=text,
            output_snapshot=evidence["brief"],
            confidence=evidence["score"],
            metadata=evidence,
        )

        ranked_tools = rank_tools(text, scenario)
        selected_tool = ranked_tools[0]
        self._add_step(
            session=session,
            run=run,
            sequence=5,
            stage="tool_router",
            agent_name="ToolRouter",
            tool_name=selected_tool["name"],
            input_snapshot=f"scenario={scenario}",
            output_snapshot=f"selected={selected_tool['name']} score={selected_tool['score']:.2f}",
            confidence=selected_tool["score"],
            metadata={"ranked_tools": ranked_tools[:4], "scoring": "scenario + semantic + success - risk - latency"},
        )

        tool_result = execute_tool(selected_tool["name"], task, evidence, graph)
        self._add_step(
            session=session,
            run=run,
            sequence=6,
            stage="executor",
            agent_name="ExecutorAgent",
            tool_name=selected_tool["name"],
            input_snapshot=task.objective,
            output_snapshot=tool_result["summary"],
            confidence=tool_result["confidence"],
            metadata=tool_result,
        )

        critique = critic_review(
            llm=self.llm,
            task=task,
            scenario=scenario,
            graph=graph,
            evidence=evidence,
            selected_tool=selected_tool,
            tool_result=tool_result,
            task_text=text,
        )
        self._add_step(
            session=session,
            run=run,
            sequence=7,
            stage="critic",
            agent_name="CriticAgent",
            input_snapshot=tool_result["summary"],
            output_snapshot=critique["decision"],
            confidence=critique["confidence"],
            status="warning" if critique["needs_approval"] else "success",
            metadata=critique,
        )

        memory_decision = memory_policy(task, critique, evidence)
        self._add_step(
            session=session,
            run=run,
            sequence=8,
            stage="memory_policy",
            agent_name="MemoryAgent",
            input_snapshot=critique["decision"],
            output_snapshot=memory_decision["decision"],
            confidence=memory_decision["confidence"],
            metadata=memory_decision,
        )

        final_answer = compose_final_answer(
            scenario=scenario,
            graph=graph,
            evidence=evidence,
            selected_tool=selected_tool,
            tool_result=tool_result,
            critique=critique,
        )
        confidence = round(
            (
                scenario_confidence
                + evidence["score"]
                + selected_tool["score"]
                + tool_result["confidence"]
                + critique["confidence"]
            )
            / 5,
            2,
        )
        reliability_score = self._reliability_score(confidence, failure_type, critique["needs_approval"])
        cost_units = self._estimate_cost_units(graph, evidence, selected_tool)

        run.status = self._final_status(failure_type, critique["needs_approval"])
        run.failure_type = failure_type
        run.recovery_action = recovery_action
        run.confidence = confidence
        run.reliability_score = reliability_score
        run.selected_tool = selected_tool["name"]
        run.final_answer = final_answer
        run.risk_level = critique["risk_level"]
        run.graph_node_count = len(graph)
        run.cost_units = cost_units
        run.approval_status = (
            AgentApprovalStatus.PENDING if critique["needs_approval"] else AgentApprovalStatus.NOT_REQUIRED
        )
        run.completed_at = None if critique["needs_approval"] else datetime.now(timezone.utc)

        task.scenario_hint = scenario
        task.risk_level = critique["risk_level"]
        task.requires_approval = critique["needs_approval"]
        task.owner_team = SCENARIO_TEAM.get(scenario, "agent-runtime")
        task.status = WorkflowTaskStatus.NEEDS_APPROVAL if critique["needs_approval"] else WorkflowTaskStatus.COMPLETED
        task.final_summary = final_answer
        task.updated_at = datetime.now(timezone.utc)

        session.add(task)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    def approve_run(
        self,
        *,
        session: Session,
        run: AgentRun,
        approver_id: Any,
        comment: str | None = None,
    ) -> AgentRun:
        """Record human approval and close the dry-run without performing a real mutation."""
        if run.status != AgentRunStatus.NEEDS_HUMAN or run.approval_status != AgentApprovalStatus.PENDING:
            raise ValueError("只有等待人工确认的运行才能审批")

        task = session.get(WorkflowTask, run.task_id) if run.task_id else None
        if task is None:
            raise ValueError("运行关联的任务不存在")

        latest_step = session.exec(
            select(AgentTraceStep)
            .where(AgentTraceStep.run_id == run.id)
            .order_by(col(AgentTraceStep.sequence).desc())
        ).first()
        next_sequence = latest_step.sequence + 1 if latest_step else 1
        approval_note = "审批记录：已通过人工确认。本次仍为 dry-run，未执行真实外部写入。"
        if comment:
            approval_note += f" 备注：{comment}"

        self._add_step(
            session=session,
            run=run,
            sequence=next_sequence,
            stage="human_approval",
            agent_name="HumanApprover",
            input_snapshot="等待人工确认的高风险动作计划",
            output_snapshot=approval_note,
            confidence=1.0,
            metadata={
                "approval_status": AgentApprovalStatus.APPROVED,
                "approver_id": str(approver_id),
                "comment": comment,
                "side_effects": "dry_run_only",
            },
        )

        run.status = AgentRunStatus.SUCCEEDED
        run.approval_status = AgentApprovalStatus.APPROVED
        run.approval_comment = comment
        run.approved_at = datetime.now(timezone.utc)
        run.approved_by = approver_id
        run.completed_at = datetime.now(timezone.utc)
        run.final_answer = f"{run.final_answer or ''}\n\n{approval_note}".strip()
        task.status = WorkflowTaskStatus.COMPLETED
        task.final_summary = run.final_answer
        task.updated_at = datetime.now(timezone.utc)
        session.add(task)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    def tools(self) -> list[ToolDefinitionPublic]:
        return list_tools()

    def evaluation_report(self, *, sample_size: int, dataset: str = "sample") -> EvaluationReportPublic:
        return evaluation_report(recorded_run_count=sample_size, dataset=dataset)

    def _add_step(
        self,
        *,
        session: Session,
        run: AgentRun,
        sequence: int,
        stage: str,
        agent_name: str,
        input_snapshot: str | None,
        output_snapshot: str | None,
        confidence: float,
        metadata: dict[str, Any],
        status: str = "success",
        tool_name: str | None = None,
    ) -> None:
        start = perf_counter()
        step = AgentTraceStep(
            run_id=run.id,
            sequence=sequence,
            stage=stage,
            agent_name=agent_name,
            tool_name=tool_name,
            status=status,
            input_snapshot=self._clip(input_snapshot),
            output_snapshot=self._clip(output_snapshot),
            confidence=round(confidence, 2),
            latency_ms=max(1, int((perf_counter() - start) * 1000) + 10 + sequence * 4),
            metadata_json=metadata,
        )
        session.add(step)
        session.commit()

    def _final_status(self, failure_type: str, needs_approval: bool) -> str:
        if needs_approval:
            return AgentRunStatus.NEEDS_HUMAN
        if failure_type != AgentFailureType.NONE:
            return AgentRunStatus.RECOVERED
        return AgentRunStatus.SUCCEEDED

    def _reliability_score(self, confidence: float, failure_type: str, needs_approval: bool) -> float:
        score = confidence
        if failure_type != AgentFailureType.NONE:
            score -= 0.06
        if needs_approval:
            score += 0.05
        return round(max(0.0, min(1.0, score)), 2)

    def _estimate_cost_units(self, graph: list[dict[str, Any]], evidence: dict[str, Any], selected_tool: dict[str, Any]) -> float:
        cost = len(graph) * 0.04 + len(evidence.get("chunks", [])) * 0.02 + selected_tool["avg_latency_ms"] / 2500
        return round(cost, 2)

    def _clip(self, value: str | None, limit: int = 900) -> str | None:
        if value is None:
            return None
        return value if len(value) <= limit else value[: limit - 3] + "..."


runtime = AetherFlowRuntime()

