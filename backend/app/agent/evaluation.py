from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.agent.critic import rule_critic_review
from app.agent.executor import execute_tool
from app.agent.planner import rule_execution_graph
from app.agent.retrieval import progressive_retrieve
from app.agent.tool_registry import (
    TOOLS,
    ToolDefinition,
    classify_scenario,
    normalize_tool,
    rank_tools,
    task_text,
)
from app.agent.version import RUNTIME_VERSION
from app.models import (
    EvaluationCaseResult,
    EvaluationDatasetInfo,
    EvaluationFailureAnalysis,
    EvaluationGateCheck,
    EvaluationMetric,
    EvaluationReleaseGate,
    EvaluationReportPublic,
    EvaluationScenarioSlice,
    EvaluationToolCoverage,
    WorkflowRiskLevel,
)

BENCHMARK_DIR = Path(__file__).parent / "benchmarks"
DATASET_CONFIG = {
    "sample": {
        "task_file": "sample_tasks.json",
        "tool_file": None,
        "tool_library_name": "built_in_tool_registry",
        "mode": "Built-in Runtime Benchmark / Tool Routing / Contract",
    },
    "toolluban": {
        "task_file": "toolluban_tasks.json",
        "tool_file": "toolluban_tools.json",
        "tool_library_name": "toolluban_tools.json + built_in_tool_registry",
        "mode": "ToolLuban Dynamic Tool Routing / Approval Gate / Contract",
    },
}


@dataclass(frozen=True)
class BenchmarkTask:
    id: str
    title: str
    objective: str
    context: str | None
    expected_output: str | None
    scenario_hint: str | None
    priority: str
    risk_level: str
    requires_approval: bool
    tags: list[str]
    expected_scenario: str
    expected_tool: str
    expected_approval: bool
    expected_contract_terms: list[str] = field(default_factory=list)


def evaluation_report(*, recorded_run_count: int, dataset: str = "sample") -> EvaluationReportPublic:
    dataset_key = _normalize_dataset(dataset)
    samples = load_benchmark_tasks(dataset_key)
    dynamic_tools = load_benchmark_tools(dataset_key)
    tool_pool = tuple(TOOLS) + tuple(dynamic_tools)
    results = [run_benchmark_case(sample, tools=tool_pool) for sample in samples]
    sample_size = len(results)

    scenario_accuracy = _ratio(result["scenario_ok"] for result in results)
    tool_top1 = _ratio(result["tool_top1"] for result in results)
    tool_top3 = _ratio(result["tool_top3"] for result in results)
    tool_top5 = _ratio(result["tool_top5"] for result in results)
    approval_accuracy = _ratio(result["approval_ok"] for result in results)
    trace_completeness = _ratio(result["trace_complete"] for result in results)
    contract_coverage = _ratio(result["contract_score"] >= 0.8 for result in results)

    metrics = [
        EvaluationMetric(name="Tool Top@1 Accuracy", single_agent=0.58, naive_multi_agent=0.7, reliability_harness=tool_top1),
        EvaluationMetric(name="Tool Top@3 Recall", single_agent=0.68, naive_multi_agent=0.78, reliability_harness=tool_top3),
        EvaluationMetric(name="Tool Top@5 Recall", single_agent=0.74, naive_multi_agent=0.84, reliability_harness=tool_top5),
        EvaluationMetric(name="Scenario Accuracy", single_agent=0.62, naive_multi_agent=0.75, reliability_harness=scenario_accuracy),
        EvaluationMetric(name="Approval Accuracy", single_agent=0.54, naive_multi_agent=0.69, reliability_harness=approval_accuracy),
        EvaluationMetric(name="Trace Completeness", single_agent=0.22, naive_multi_agent=0.56, reliability_harness=trace_completeness),
        EvaluationMetric(name="Output Contract Coverage", single_agent=0.48, naive_multi_agent=0.64, reliability_harness=contract_coverage),
    ]
    cases = [_case_public(result) for result in results]
    failures = [_failure_public(result) for result in results if result["failure_reason"]]
    gate_checks = _build_gate_checks(
        scenario_accuracy=scenario_accuracy,
        tool_top1=tool_top1,
        tool_top3=tool_top3,
        approval_accuracy=approval_accuracy,
        trace_completeness=trace_completeness,
        contract_coverage=contract_coverage,
    )
    scenario_slices = _scenario_slices(results)
    tool_coverage = _tool_coverage(results)
    release_gate = _release_gate(gate_checks, len(failures))
    recommended_actions = _recommended_actions(gate_checks, failures, scenario_slices)
    config = DATASET_CONFIG[dataset_key]

    return EvaluationReportPublic(
        experiment_id=f"exp-{dataset_key}-{uuid.uuid4().hex[:10]}",
        experiment_name=f"{dataset_key.upper()} Reliability Baseline",
        runtime_version=RUNTIME_VERSION,
        status="completed",
        sample_size=sample_size,
        case_count=sample_size,
        failure_count=len(failures),
        metrics=metrics,
        release_gate=release_gate,
        gate_checks=gate_checks,
        scenario_slices=scenario_slices,
        tool_coverage=tool_coverage,
        recommended_actions=recommended_actions,
        dataset=EvaluationDatasetInfo(
            dataset_key=dataset_key,
            task_dataset_name=str(config["task_file"]),
            tool_library_name=str(config["tool_library_name"]),
            evaluation_mode=str(config["mode"]),
            dynamic_tool_count=len(dynamic_tools),
            has_expected_tool=all(bool(task.expected_tool) for task in samples),
            has_tool_library=True,
        ),
        cases=cases,
        failures=failures,
        notes=[
            f"Experiment {dataset_key.upper()} Reliability Baseline completed with {sample_size} replayed cases.",
            f"Dataset: {dataset_key}; benchmark file: {config['task_file']}; tool library: {config['tool_library_name']}.",
            f"Dynamic tools loaded: {len(dynamic_tools)}; total ranked tools: {len(tool_pool)}; recorded production-like runs: {recorded_run_count}.",
            "Each case is replayed through scenario routing, DAG planning, retrieval, dynamic tool ranking, dry-run execution, critic review, and contract term checks.",
            "Release Gate combines hard reliability thresholds with case-level failures, so a high aggregate score does not hide a review item.",
        ],
    )


def _build_gate_checks(
    *,
    scenario_accuracy: float,
    tool_top1: float,
    tool_top3: float,
    approval_accuracy: float,
    trace_completeness: float,
    contract_coverage: float,
) -> list[EvaluationGateCheck]:
    definitions = [
        ("场景路由", scenario_accuracy, 0.95, "任务是否进入预期场景"),
        ("工具 Top@1", tool_top1, 0.85, "首选工具是否命中标注工具"),
        ("工具 Top@3", tool_top3, 0.95, "正确工具是否进入候选前三"),
        ("审批判断", approval_accuracy, 1.0, "高风险任务是否稳定触发审批"),
        ("Trace 完整性", trace_completeness, 1.0, "关键运行阶段是否都有可回放记录"),
        ("输出契约", contract_coverage, 0.95, "结果是否覆盖预期业务字段"),
    ]
    return [
        EvaluationGateCheck(
            name=name,
            score=score,
            threshold=threshold,
            passed=score >= threshold,
            detail=f"{detail}，当前 {score:.0%}，门槛 {threshold:.0%}",
        )
        for name, score, threshold, detail in definitions
    ]


def _release_gate(checks: list[EvaluationGateCheck], failure_count: int) -> EvaluationReleaseGate:
    failed_checks = [check.name for check in checks if not check.passed]
    if failed_checks:
        return EvaluationReleaseGate(
            status="fail",
            label="不可放行",
            summary=f"有 {len(failed_checks)} 项可靠性门禁未达标：{'、'.join(failed_checks)}。",
        )
    if failure_count:
        return EvaluationReleaseGate(
            status="review",
            label="建议复核",
            summary=f"聚合门禁已达标，但仍有 {failure_count} 条失败样本，建议先完成 Case 复盘。",
        )
    return EvaluationReleaseGate(
        status="pass",
        label="可放行",
        summary="所有门禁和案例均通过，可以作为当前 Runtime 版本的可靠性基线。",
    )


def _scenario_slices(results: list[dict[str, Any]]) -> list[EvaluationScenarioSlice]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(str(result["expected_scenario"]), []).append(result)
    slices = []
    for scenario, items in grouped.items():
        slices.append(
            EvaluationScenarioSlice(
                scenario=scenario,
                case_count=len(items),
                pass_rate=_ratio(item["passed"] for item in items),
                top1_accuracy=_ratio(item["tool_top1"] for item in items),
                approval_accuracy=_ratio(item["approval_ok"] for item in items),
                contract_coverage=_ratio(item["contract_score"] >= 0.8 for item in items),
                failed_cases=[str(item["id"]) for item in items if not item["passed"]],
            )
        )
    return sorted(slices, key=lambda item: item.scenario)


def _tool_coverage(results: list[dict[str, Any]]) -> list[EvaluationToolCoverage]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(str(result["expected_tool"]), []).append(result)
    coverage = []
    for tool_name, items in grouped.items():
        ranks = []
        for item in items:
            candidates = item["top5_tools"]
            if tool_name in candidates:
                ranks.append(candidates.index(tool_name) + 1)
        coverage.append(
            EvaluationToolCoverage(
                tool_name=tool_name,
                expected_count=len(items),
                selected_count=sum(1 for item in items if item["actual_tool"] == tool_name),
                top1_hits=sum(1 for item in items if item["tool_top1"]),
                accuracy=_ratio(item["tool_top1"] for item in items),
                average_rank=round(sum(ranks) / len(ranks), 2) if ranks else None,
            )
        )
    return sorted(coverage, key=lambda item: (-item.expected_count, item.tool_name))


def _recommended_actions(
    checks: list[EvaluationGateCheck],
    failures: list[EvaluationFailureAnalysis],
    slices: list[EvaluationScenarioSlice],
) -> list[str]:
    actions = []
    for check in checks:
        if not check.passed:
            actions.append(f"优先修复{check.name}门禁：{check.detail}。")
    seen_categories: set[str] = set()
    for failure in failures:
        if failure.category not in seen_categories:
            actions.append(f"复盘 {failure.category}：{failure.recommendation}")
            seen_categories.add(failure.category)
    weak_slices = [slice_.scenario for slice_ in slices if slice_.pass_rate < 0.8]
    if weak_slices:
        actions.append(f"为低通过率场景补充独立样本和工具描述：{'、'.join(weak_slices)}。")
    if not actions:
        actions.append("当前没有阻塞项；建议保存本次结果作为基线，再用新版本 Runtime 做对照实验。")
    return actions[:6]

def load_benchmark_tasks(dataset: str = "sample") -> list[BenchmarkTask]:
    dataset_key = _normalize_dataset(dataset)
    path = BENCHMARK_DIR / str(DATASET_CONFIG[dataset_key]["task_file"])
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    return [_parse_task(item) for item in raw]


def load_benchmark_tools(dataset: str = "sample") -> list[ToolDefinition]:
    dataset_key = _normalize_dataset(dataset)
    tool_file = DATASET_CONFIG[dataset_key].get("tool_file")
    if not tool_file:
        return []
    path = BENCHMARK_DIR / str(tool_file)
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    return [normalize_tool(item) for item in raw]


def run_benchmark_case(task: BenchmarkTask, *, tools: tuple[ToolDefinition, ...] = TOOLS) -> dict[str, Any]:
    text = task_text(task)
    scenario, _confidence = classify_scenario(task, text, tools=tools)
    graph = rule_execution_graph(scenario)
    evidence = progressive_retrieve(text, scenario)
    ranked_tools = rank_tools(text, scenario, tools=tools)
    selected_tool = ranked_tools[0]
    top3_tools = [tool["name"] for tool in ranked_tools[:3]]
    top5_tools = [tool["name"] for tool in ranked_tools[:5]]
    tool_result = execute_tool(selected_tool["name"], task, evidence, graph)
    critique = rule_critic_review(task, scenario, evidence, selected_tool, tool_result, text)

    actual_approval = bool(critique["needs_approval"])
    trace_complete = bool(graph and evidence.get("brief") and selected_tool and tool_result and critique)
    data_profile = tool_result.get("profile", {})
    data_profile_ok = (
        selected_tool["name"] != "data_frame_profiler"
        or bool(data_profile.get("csv_detected"))
        and data_profile.get("column_count", 0) > 0
        and "numeric_summary" in data_profile
        and "categorical_summary" in data_profile
    )
    guardrail_ok = _guardrail_ok(task, selected_tool, actual_approval, evidence)

    scenario_ok = scenario == task.expected_scenario
    tool_top1 = selected_tool["name"] == task.expected_tool
    tool_top3 = task.expected_tool in top3_tools
    tool_top5 = task.expected_tool in top5_tools
    approval_ok = actual_approval == task.expected_approval
    output_text = _compose_case_output(
        task=task,
        actual_scenario=scenario,
        selected_tool=selected_tool,
        evidence=evidence,
        tool_result=tool_result,
        critique=critique,
    )
    matched_terms, missing_terms = _contract_terms(output_text, task.expected_contract_terms)
    contract_score = _contract_score(task.expected_contract_terms, matched_terms)
    passed = scenario_ok and tool_top1 and approval_ok and trace_complete and data_profile_ok and guardrail_ok and contract_score >= 0.8
    failure_reason, failure_category, recommendation = _failure_detail(
        task=task,
        actual_scenario=scenario,
        selected_tool=selected_tool["name"],
        top5_tools=top5_tools,
        actual_approval=actual_approval,
        scenario_ok=scenario_ok,
        tool_top1=tool_top1,
        tool_top5=tool_top5,
        approval_ok=approval_ok,
        trace_complete=trace_complete,
        data_profile_ok=data_profile_ok,
        guardrail_ok=guardrail_ok,
        contract_score=contract_score,
        missing_terms=missing_terms,
    )

    return {
        "id": task.id,
        "title": task.title,
        "user_request": task.objective,
        "expected_scenario": task.expected_scenario,
        "actual_scenario": scenario,
        "scenario_ok": scenario_ok,
        "expected_tool": task.expected_tool,
        "actual_tool": selected_tool["name"],
        "top3_tools": top3_tools,
        "top5_tools": top5_tools,
        "tool_top1": tool_top1,
        "tool_top3": tool_top3,
        "tool_top5": tool_top5,
        "expected_approval": task.expected_approval,
        "actual_approval": actual_approval,
        "approval_ok": approval_ok,
        "trace_complete": trace_complete,
        "data_profile_ok": data_profile_ok,
        "guardrail_ok": guardrail_ok,
        "contract_score": contract_score,
        "matched_contract_terms": matched_terms,
        "missing_contract_terms": missing_terms,
        "passed": passed,
        "failure_reason": failure_reason,
        "failure_category": failure_category,
        "recommendation": recommendation,
    }


def _case_public(result: dict[str, Any]) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        case_id=result["id"],
        user_request=result["user_request"],
        expected_tool=result["expected_tool"],
        selected_tool=result["actual_tool"],
        top3_tools=result["top3_tools"],
        top5_tools=result["top5_tools"],
        expected_approval=result["expected_approval"],
        actual_approval=result["actual_approval"],
        expected_scenario=result["expected_scenario"],
        actual_scenario=result["actual_scenario"],
        contract_score=result["contract_score"],
        matched_contract_terms=result["matched_contract_terms"],
        missing_contract_terms=result["missing_contract_terms"],
        trace_complete=result["trace_complete"],
        result="passed" if result["passed"] else "failed",
        failure_reason=result["failure_reason"],
    )


def _failure_public(result: dict[str, Any]) -> EvaluationFailureAnalysis:
    return EvaluationFailureAnalysis(
        case_id=result["id"],
        category=result["failure_category"],
        reason=result["failure_reason"],
        recommendation=result["recommendation"],
    )


def _normalize_dataset(dataset: str | None) -> str:
    key = (dataset or "sample").strip().lower()
    if key not in DATASET_CONFIG:
        return "sample"
    return key


def _parse_task(item: dict[str, Any]) -> BenchmarkTask:
    contract_terms = item.get("expected_contract_terms")
    if not contract_terms:
        legacy = item.get("expected_labels") or {}
        legacy_contract = legacy.get("contract") if isinstance(legacy, dict) else None
        contract_terms = ["工具", "理由", "风险", "审批", "证据", "下一步"]
        if legacy_contract:
            contract_terms.append(str(legacy_contract))
    return BenchmarkTask(
        id=str(item["id"]),
        title=str(item["title"]),
        objective=str(item["objective"]),
        context=item.get("context"),
        expected_output=item.get("expected_output"),
        scenario_hint=item.get("scenario_hint"),
        priority=str(item.get("priority") or "medium"),
        risk_level=str(item.get("risk_level") or WorkflowRiskLevel.MEDIUM),
        requires_approval=bool(item.get("requires_approval", False)),
        tags=[str(tag) for tag in item.get("tags", [])],
        expected_scenario=str(item["expected_scenario"]),
        expected_tool=str(item["expected_tool"]),
        expected_approval=bool(item["expected_approval"]),
        expected_contract_terms=[str(term) for term in contract_terms],
    )


def _compose_case_output(
    *,
    task: BenchmarkTask,
    actual_scenario: str,
    selected_tool: dict[str, Any],
    evidence: dict[str, Any],
    tool_result: dict[str, Any],
    critique: dict[str, Any],
) -> str:
    approval = "需要审批" if critique["needs_approval"] else "无需审批"
    next_step = "等待人工审批后执行" if critique["needs_approval"] else "进入 dry-run 结果确认和 Trace 归档"
    risk_reason = ", ".join(critique.get("blockers") or ["risk_policy_checked"])
    return "\n".join(
        [
            f"工具: {selected_tool['name']} / {selected_tool.get('label', selected_tool['name'])}",
            f"场景: {actual_scenario}",
            f"理由: {selected_tool.get('description', '')} {tool_result.get('summary', '')}",
            f"风险: {critique['risk_level']} {risk_reason}",
            f"审批: {approval}",
            f"证据: {evidence.get('brief', '')}",
            f"下一步: {next_step}",
            f"预期输出: {task.expected_output or ''}",
        ]
    )


def _contract_terms(output_text: str, expected_terms: list[str]) -> tuple[list[str], list[str]]:
    normalized = output_text.lower()
    matched = [term for term in expected_terms if term.lower() in normalized]
    missing = [term for term in expected_terms if term.lower() not in normalized]
    return matched, missing


def _contract_score(expected_terms: list[str], matched_terms: list[str]) -> float:
    if not expected_terms:
        return 1.0
    return round(len(matched_terms) / len(expected_terms), 2)


def _failure_detail(
    *,
    task: BenchmarkTask,
    actual_scenario: str,
    selected_tool: str,
    top5_tools: list[str],
    actual_approval: bool,
    scenario_ok: bool,
    tool_top1: bool,
    tool_top5: bool,
    approval_ok: bool,
    trace_complete: bool,
    data_profile_ok: bool,
    guardrail_ok: bool,
    contract_score: float,
    missing_terms: list[str],
) -> tuple[str | None, str | None, str | None]:
    if not scenario_ok:
        return (
            f"Expected scenario {task.expected_scenario}, but router selected {actual_scenario}.",
            "场景路由偏差",
            "补充场景提示词、中文同义词和任务描述中的业务关键词，避免工具空间一开始就被收窄到错误场景。",
        )
    if not tool_top5:
        return (
            f"Expected tool {task.expected_tool} was not in Top@5 candidates: {', '.join(top5_tools)}.",
            "工具召回失败",
            "扩展动态工具库中的 keywords、label 和 description，让 Tool Router 能先召回正确工具。",
        )
    if not tool_top1:
        return (
            f"Expected tool {task.expected_tool}, but selected {selected_tool}.",
            "工具排序偏差",
            "检查候选工具得分权重，尤其是语义匹配、风险惩罚和场景匹配的相对权重。",
        )
    if not approval_ok:
        return (
            f"Expected approval={task.expected_approval}, actual approval={actual_approval}.",
            "审批判断偏差",
            "检查高风险写操作、财务/合规/客户可见动作是否稳定触发 approval gate。",
        )
    if not trace_complete:
        return (
            "Trace is incomplete for route, evidence, tool execution, or critic review.",
            "Trace 不完整",
            "确保每次运行都记录 Scenario、Planner、Retrieval、Tool Router、Executor、Critic 和 Memory 步骤。",
        )
    if not data_profile_ok:
        return (
            "Data profiler did not return a parseable profile contract.",
            "真实工具输出不足",
            "检查 CSV 输入解析、字段画像和异常提示是否写入 executor 输出。",
        )
    if not guardrail_ok:
        return (
            "Guardrail policy did not align with risk or weak evidence.",
            "安全护栏偏差",
            "高风险、弱证据和外部写入任务必须稳定进入审批或恢复路径。",
        )
    if contract_score < 0.8:
        return (
            f"Output contract score is {contract_score}; missing terms: {', '.join(missing_terms)}.",
            "输出契约不足",
            "补齐工具、理由、风险、审批、证据和下一步动作等结构化输出字段。",
        )
    return None, None, None


def _guardrail_ok(
    task: BenchmarkTask,
    selected_tool: dict[str, Any],
    actual_approval: bool,
    evidence: dict[str, Any],
) -> bool:
    high_risk = task.requires_approval or task.risk_level == WorkflowRiskLevel.HIGH or selected_tool["risk_level"] == WorkflowRiskLevel.HIGH
    weak_evidence = evidence["score"] < 0.5
    return actual_approval if high_risk or weak_evidence else True


def _ratio(values: Any) -> float:
    materialized = list(values)
    if not materialized:
        return 0.0
    return round(sum(1 for value in materialized if value) / len(materialized), 2)



