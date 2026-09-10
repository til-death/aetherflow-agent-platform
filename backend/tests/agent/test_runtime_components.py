from types import SimpleNamespace

import pytest

from app.agent.evaluation import (
    load_benchmark_tasks,
    load_benchmark_tools,
    run_benchmark_case,
)
from app.agent.executor import profile_csv_payload
from app.agent.planner import rule_execution_graph
from app.agent.schemas import ExecutionGraphPlan
from app.agent.tool_registry import TOOLS, classify_scenario, rank_tools, task_text
from app.agent.validators import AgentValidationError, validate_execution_plan


def make_task(**overrides: object) -> SimpleNamespace:
    values = {
        "title": "分析销售数据",
        "objective": "分析本月销售数据，识别异常并给出建议",
        "context": None,
        "expected_output": "指标摘要和异常提示",
        "scenario_hint": "analysis",
        "priority": "medium",
        "risk_level": "low",
        "requires_approval": False,
        "tags": ["数据", "分析"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_csv_profiler_supports_bilingual_data_and_returns_actionable_hints() -> None:
    payload = """产品,Region,销售额,Orders
Aether One,华东,128000,320
Aether One,East,97000,245
Flow Desk,华东,,180
Flow Desk,East,45000,165
Legacy Box,East,1200,12
Legacy Box,East,1200,12
"""

    profile = profile_csv_payload(payload)

    assert profile["csv_detected"] is True
    assert profile["column_count"] == 4
    assert profile["row_count"] == 6
    assert profile["columns_with_missing"] == 1
    assert profile["missing_values"]["销售额"] == 1
    assert profile["numeric_summary"]["销售额"]["max"] == 128000.0
    assert profile["categorical_summary"]["Region"]["unique"] == 2
    assert profile["anomaly_hints"]


def test_router_prefers_analysis_and_profiler_for_csv_task() -> None:
    task = make_task(context="产品,区域,销售额\nA,华东,100\nB,华南,80")
    text = task_text(task)
    scenario, confidence = classify_scenario(task, text, tools=TOOLS)
    ranked = rank_tools(text, scenario, tools=TOOLS)

    assert scenario == "analysis"
    assert confidence >= 0.88
    assert ranked[0]["name"] == "data_frame_profiler"


def test_external_graph_contains_approval_gate_and_memory_policy() -> None:
    graph = rule_execution_graph("external_api")
    ids = [node["id"] for node in graph]

    assert "approval_gate" in ids
    assert ids[-1] == "memory_policy"
    assert graph[-1]["depends_on"] == ["critic_validate"]


def test_validator_rejects_cycle_before_plan_can_execute() -> None:
    plan = ExecutionGraphPlan.model_validate(
        {
            "objective_summary": "Validate an external action before execution",
            "estimated_risk": "high",
            "nodes": [
                {
                    "id": "normalize_task",
                    "description": "Normalize the incoming task contract",
                    "agent": "PlannerAgent",
                    "scenario": "external_api",
                    "depends_on": ["approval_gate"],
                    "expected_output_type": "task_contract",
                    "risk_level": "high",
                    "allowed_tools": [],
                },
                {
                    "id": "retrieve_evidence",
                    "description": "Retrieve evidence for the proposed action",
                    "agent": "RAGAgent",
                    "scenario": "external_api",
                    "depends_on": ["normalize_task"],
                    "expected_output_type": "evidence_bundle",
                    "risk_level": "medium",
                    "allowed_tools": [],
                },
                {
                    "id": "approval_gate",
                    "description": "Pause for explicit human confirmation",
                    "agent": "CriticAgent",
                    "scenario": "external_api",
                    "depends_on": ["retrieve_evidence"],
                    "expected_output_type": "approval_checkpoint",
                    "risk_level": "high",
                    "allowed_tools": ["approval_gate"],
                },
                {
                    "id": "critic_validate",
                    "description": "Review evidence, risk, and approval state",
                    "agent": "CriticAgent",
                    "scenario": "external_api",
                    "depends_on": ["approval_gate"],
                    "expected_output_type": "validation_decision",
                    "risk_level": "high",
                    "allowed_tools": [],
                },
            ],
        }
    )

    with pytest.raises(AgentValidationError, match="cycle"):
        validate_execution_plan(plan, allowed_tool_names={"approval_gate"})


def test_sample_benchmark_replay_returns_contract_fields() -> None:
    tasks = load_benchmark_tasks("sample")
    result = run_benchmark_case(tasks[0])

    assert len(tasks) == 10
    assert result["trace_complete"] is True
    assert result["contract_score"] >= 0.8
    assert {"工具", "理由", "风险", "审批", "证据", "下一步"}.issubset(
        result["matched_contract_terms"]
    )


def test_memory_policy_does_not_gate_when_risky_policy_is_only_content() -> None:
    tasks = load_benchmark_tasks("sample")
    memory_task = next(task for task in tasks if task.id == "memory_001")
    result = run_benchmark_case(memory_task)

    assert result["actual_tool"] == "memory_write_policy"
    assert result["actual_approval"] is False
    assert result["passed"] is True


def test_dynamic_tool_metadata_breaks_general_scenario_ties() -> None:
    tasks = load_benchmark_tasks("toolluban")
    task = next(item for item in tasks if item.id == "tlb_memory_001")
    tools = tuple(TOOLS) + tuple(load_benchmark_tools("toolluban"))
    ranked = rank_tools(task_text(task), "general", tools=tools)

    assert ranked[0]["name"] == "toolluban_preference_extractor"
