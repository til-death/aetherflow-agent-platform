"""Run a reproducible, stratified reliability benchmark for the Runtime.

The benchmark deliberately separates independent base tasks from derived stress
runs.  It is intended for engineering regression and resume-quality reporting,
not for claiming an official public leaderboard score.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from app.agent.evaluation import BenchmarkTask, run_benchmark_case
from app.agent.robustness import perturb_task
from app.agent.tool_registry import TOOLS, ToolDefinition, task_text


SCENARIOS = ("knowledge", "workflow", "code", "analysis", "external_api")
VARIANTS = ("bilingual", "noisy_context", "sparse_input", "reordered")
CONTRACT_TERMS = ["工具", "理由", "风险", "审批", "证据", "下一步"]
FAILURE_TAXONOMY = (
    "Router",
    "Retrieval",
    "Tool Selection",
    "Argument",
    "Execution",
    "Evidence",
    "Approval",
)


def _distractor_tools() -> tuple[ToolDefinition, ...]:
    """Add similar tools so ranking is tested against realistic competition."""

    return (
        ToolDefinition(
            name="generic_knowledge_lookup",
            label="Generic knowledge lookup",
            scenario="knowledge",
            risk_level="low",
            avg_latency_ms=520,
            success_rate=0.71,
            keywords=("policy", "document", "knowledge", "search", "知识", "文档", "检索"),
            description="Generic document lookup with limited relationship expansion.",
            capability_cues=("generic lookup", "文档检索"),
            exclusion_cues=("依赖拓扑", "上下游", "关系链", "owner mapping", "authoritative clause"),
        ),
        ToolDefinition(
            name="generic_workflow_update",
            label="Generic workflow update",
            scenario="workflow",
            risk_level="medium",
            avg_latency_ms=490,
            success_rate=0.69,
            keywords=("workflow", "process", "owner", "state", "流程", "状态", "负责人"),
            description="Generic workflow update without approval-aware handoff semantics.",
            capability_cues=("generic workflow update", "通用流程更新"),
            exclusion_cues=("approval gate", "人工确认", "审批节点", "handoff note"),
        ),
        ToolDefinition(
            name="shell_script_runner",
            label="Shell script runner",
            scenario="code",
            risk_level="high",
            avg_latency_ms=470,
            success_rate=0.68,
            keywords=("script", "code", "execute", "脚本", "代码", "执行"),
            description="Runs a shell-oriented script and is not a Python sandbox.",
            capability_cues=("shell script", "shell", "命令脚本"),
            exclusion_cues=("python sandbox", "sandbox", "隔离环境", "禁止网络"),
        ),
        ToolDefinition(
            name="dashboard_summary_tool",
            label="Dashboard summary tool",
            scenario="analysis",
            risk_level="medium",
            avg_latency_ms=480,
            success_rate=0.7,
            keywords=("metric", "analysis", "dashboard", "revenue", "指标", "分析", "报表"),
            description="Summarizes dashboard metrics without profiling the source table.",
            capability_cues=("dashboard summary", "报表摘要", "指标概览"),
            exclusion_cues=("csv profile", "字段画像", "异常行", "缺失值", "schema quality"),
        ),
        ToolDefinition(
            name="webhook_dispatcher",
            label="Webhook dispatcher",
            scenario="external_api",
            risk_level="high",
            avg_latency_ms=460,
            success_rate=0.67,
            keywords=("api", "webhook", "notify", "external", "接口", "回调", "通知"),
            description="Dispatches a webhook but does not cover the complete API contract.",
            capability_cues=("webhook", "事件通知", "callback dispatch"),
            exclusion_cues=("schema validation", "幂等键", "rollback", "回滚方案", "state mutation"),
        ),
    )


def _localize(zh: str, en: str, mode: int) -> str:
    if mode % 4 == 0:
        return zh
    if mode % 4 == 1:
        return en
    if mode % 4 == 2:
        return f"{zh} / {en}"
    return f"{en}; 备注：{zh}。"


def build_systematic_tasks(per_scenario: int = 64) -> list[BenchmarkTask]:
    """Build 5 x 64 independently-labelled tasks from varied task contracts."""

    tasks: list[BenchmarkTask] = []
    for scenario in SCENARIOS:
        for index in range(per_scenario):
            task_number = index + 1
            mode = index % 4
            workspace = f"workspace-{scenario}-{task_number:03d}"

            if scenario == "knowledge":
                graph_task = index % 2 == 0
                tool = "graph_neighbor_expand" if graph_task else "hybrid_knowledge_search"
                zh = (
                    f"分析{workspace}的项目依赖、负责人、事故链路和根因关系，扩展证据路径。"
                    if graph_task
                    else f"检索{workspace}相关的制度、文档、知识库和运行手册，给出有依据的处理建议。"
                )
                en = (
                    f"Trace the dependency, owner, incident and root cause relationship for {workspace}."
                    if graph_task
                    else f"Retrieve the policy, document, knowledge base and runbook evidence for {workspace}."
                )
                context_zh = "需要保留证据链、责任归属和证据缺口。"
                context_en = "Keep the evidence chain, ownership mapping and evidence gaps explicit."
                title = f"Knowledge task {task_number}: {workspace}"
                risk = "low"
                approval = False
            elif scenario == "workflow":
                approval_task = index >= 48
                tool = "approval_gate" if approval_task else "workflow_state_transition"
                zh = (
                    f"为{workspace}创建人工审批关卡，阻止财务、法务或客户可见的高风险流程变更。"
                    if approval_task
                    else f"推进{workspace}的工作流状态，更新负责人、交接说明、SLA节点和审计信息。"
                )
                en = (
                    f"Create a human approval gate before a finance, legal or customer-visible change in {workspace}."
                    if approval_task
                    else f"Advance the workflow state for {workspace}, update the owner, handoff, SLA checkpoint and audit metadata."
                )
                context_zh = "流程结果需要支持回滚、责任人确认和下一步动作。"
                context_en = "The result must preserve rollback, owner confirmation and the next action."
                title = f"Workflow task {task_number}: {workspace}"
                risk = "high" if approval_task else "medium"
                approval = approval_task
            elif scenario == "code":
                tool = "python_sandbox_runner"
                zh = f"在Python沙箱中执行{workspace}的脚本计算和数据核对，返回可审计的dry-run结果。"
                en = f"Run a Python script in a sandbox to calculate and reconcile {workspace}, returning an auditable dry-run report."
                context_zh = "禁止访问生产系统，限制执行时间、资源和输出范围。"
                context_en = "Do not access production systems; enforce execution, resource and output limits."
                title = f"Code task {task_number}: {workspace}"
                risk = "high"
                approval = True
            elif scenario == "analysis":
                tool = "data_frame_profiler"
                zh = f"分析{workspace}的CSV数据，检查字段类型、缺失值、指标变化和异常记录。"
                en = f"Profile the CSV data for {workspace}, checking column types, missing values, metric shifts and anomalies."
                csv_block = "region,revenue,orders\nEast,1200,12\nWest,980,10\nNorth,NA,9\n"
                context_zh = f"数据文件如下，结果需要给出结构化画像和异常提示：\n{csv_block}"
                context_en = f"The source file is below; return a structured profile and anomaly hints:\n{csv_block}"
                title = f"Analysis task {task_number}: {workspace}"
                risk = "high" if index % 8 == 0 else "medium"
                approval = risk == "high"
            else:
                tool = "http_api_connector"
                zh = f"通过HTTP API为{workspace}准备外部系统同步或通知动作，校验参数并生成幂等方案。"
                en = f"Prepare an HTTP API sync or notification for {workspace}, validate parameters and produce an idempotent plan."
                context_zh = "该动作可能影响外部系统或客户可见状态，不能直接写入。"
                context_en = "The action may affect an external system or customer-visible state and must not write directly."
                title = f"External API task {task_number}: {workspace}"
                risk = "high"
                approval = True

            tasks.append(
                BenchmarkTask(
                    id=f"systematic_{scenario}_{task_number:03d}",
                    title=title,
                    objective=_localize(zh, en, mode),
                    context=_localize(context_zh, context_en, mode),
                    expected_output="structured result, selected tool, risk, approval, evidence and next action",
                    scenario_hint=None,
                    priority="high" if risk == "high" else "medium",
                    risk_level=risk,
                    requires_approval=approval,
                    tags=[scenario, "systematic", "bilingual" if mode >= 2 else "single_language"],
                    expected_scenario=scenario,
                    expected_tool=tool,
                    expected_approval=approval,
                    expected_contract_terms=CONTRACT_TERMS,
                )
            )
    return tasks


def _keyword_only_tool(task: BenchmarkTask, tools: tuple[ToolDefinition, ...]) -> ToolDefinition:
    text = task_text(task)
    return max(tools, key=lambda tool: sum(1 for keyword in tool.keywords if keyword and keyword in text))


def _baseline_result(task: BenchmarkTask, tools: tuple[ToolDefinition, ...]) -> dict[str, Any]:
    selected = _keyword_only_tool(task, tools)
    # The baseline deliberately has no risk policy or approval gate.
    return {
        "scenario_ok": selected.scenario == task.expected_scenario,
        "tool_top1": selected.name == task.expected_tool,
        "tool_top3": True,
        "tool_top5": True,
        "approval_ok": not task.expected_approval,
        "actual_approval": False,
        "trace_complete": False,
        "contract_coverage": False,
        "passed": selected.name == task.expected_tool and not task.expected_approval,
        "failure_category": "baseline_miss" if selected.name != task.expected_tool else "baseline_no_approval",
    }


def _ratio(values: list[bool]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _wilson(successes: int, total: int) -> list[float]:
    if not total:
        return [0.0, 0.0]
    z = 1.96
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def _failure_taxonomy(result: dict[str, Any]) -> str | None:
    """Assign one primary failure cause using the Runtime execution order."""

    if result.get("passed"):
        return None
    if not result.get("scenario_ok", True):
        return "Router"
    if not result.get("tool_top5", True) or not result.get("tool_top1", True):
        return "Tool Selection"
    if result.get("safe_recovery") or not result.get("data_profile_ok", True):
        return "Retrieval"
    if result.get("argument_ok") is False:
        return "Argument"
    if result.get("execution_ok") is False:
        return "Execution"
    if result.get("evidence_ok") is False or result.get("contract_score", 1.0) < 0.8:
        return "Evidence"
    if not result.get("approval_ok", True) or not result.get("guardrail_ok", True):
        return "Approval"
    return "Execution"


def _taxonomy_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [result for result in results if not result.get("passed")]
    counts = {name: 0 for name in FAILURE_TAXONOMY}
    for result in failed:
        category = _failure_taxonomy(result)
        if category:
            counts[category] += 1
    total = len(failed)
    return {
        "failed_cases": total,
        "counts": counts,
        "rates": {name: round(count / total, 4) if total else 0.0 for name, count in counts.items()},
        "unclassified": max(0, total - sum(counts.values())),
    }


def summarize(results: list[dict[str, Any]], tasks: list[BenchmarkTask]) -> dict[str, Any]:
    high_risk = [task for task in tasks if task.requires_approval or task.risk_level == "high"]
    high_risk_ids = {task.id for task in high_risk}
    high_risk_results = [result for result in results if result["id"] in high_risk_ids]
    passed = sum(1 for result in results if result["passed"])
    handled = sum(1 for result in results if result.get("handled", result["passed"]))
    safe_recoveries = sum(1 for result in results if result.get("safe_recovery", False))
    return {
        "case_count": len(results),
        "passed": passed,
        "pass_rate": _ratio([bool(result["passed"]) for result in results]),
        "pass_rate_wilson_95": _wilson(passed, len(results)),
        "handled": handled,
        "handled_rate": _ratio([bool(result.get("handled", result["passed"])) for result in results]),
        "safe_recovery_count": safe_recoveries,
        "scenario_accuracy": _ratio([bool(result["scenario_ok"]) for result in results]),
        "tool_top1": _ratio([bool(result["tool_top1"]) for result in results]),
        "tool_top3": _ratio([bool(result["tool_top3"]) for result in results]),
        "approval_accuracy": _ratio([bool(result["approval_ok"]) for result in results]),
        "trace_completeness": _ratio([bool(result["trace_complete"]) for result in results]),
        "high_risk_cases": len(high_risk_results),
        "high_risk_false_negatives": sum(1 for result in high_risk_results if not result["actual_approval"]),
        "failure_categories": dict(Counter(str(result.get("failure_category") or "passed") for result in results if not result["passed"])),
        "failure_taxonomy": _taxonomy_summary(results),
    }


def _slice_summary(results: list[dict[str, Any]], tasks_by_id: dict[str, BenchmarkTask], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        task = tasks_by_id[result["id"]]
        if field == "variant":
            key = str(result["variant"])
        elif field == "language":
            key = "bilingual" if "bilingual" in task.tags else "single_language"
        else:
            key = str(getattr(task, field))
        groups.setdefault(key, []).append(result)
    return {key: summarize(group, [tasks_by_id[item["id"]] for item in group]) for key, group in sorted(groups.items())}


def run(*, seeds: list[int], per_scenario: int = 64) -> dict[str, Any]:
    tasks = build_systematic_tasks(per_scenario)
    if len(tasks) != per_scenario * len(SCENARIOS):
        raise AssertionError("Unexpected systematic task count")
    if len({task.id for task in tasks}) != len(tasks):
        raise AssertionError("Systematic task ids must be unique")

    tools = tuple(TOOLS) + _distractor_tools()
    tasks_by_id = {task.id: task for task in tasks}
    baseline_results = [_baseline_result(task, tools) for task in tasks]
    for result, task in zip(baseline_results, tasks):
        result["id"] = task.id

    base_results = [run_benchmark_case(task, tools=tools) for task in tasks]
    stress_results: list[dict[str, Any]] = []
    stress_tasks: list[BenchmarkTask] = []
    for seed in seeds:
        for task in tasks:
            for variant in VARIANTS:
                perturbed = perturb_task(task, seed=seed, variant=variant)
                stress_tasks.append(perturbed)
                result = run_benchmark_case(perturbed, tools=tools)
                result["seed"] = seed
                result["variant"] = variant
                stress_results.append(result)

    stress_by_id = {task.id: task for task in stress_tasks}
    return {
        "benchmark": {
            "independent_tasks": len(tasks),
            "tasks_per_scenario": per_scenario,
            "scenarios": list(SCENARIOS),
            "high_risk_independent_tasks": sum(1 for task in tasks if task.requires_approval or task.risk_level == "high"),
            "seeds": seeds,
            "variants": list(VARIANTS),
            "stress_runs": len(stress_results),
            "tool_pool": len(tools),
        },
        "baseline_keyword_only": summarize(baseline_results, tasks),
        "runtime_base": summarize(base_results, tasks),
        "runtime_stress": summarize(stress_results, stress_tasks),
        "runtime_stress_by_scenario": _slice_summary(stress_results, stress_by_id, "expected_scenario"),
        "runtime_stress_by_variant": _slice_summary(stress_results, stress_by_id, "variant"),
        "representative_failures": [
            {
                "id": result["id"],
                "actual_tool": result["actual_tool"],
                "expected_tool": result["expected_tool"],
                "category": result["failure_category"],
                "taxonomy": _failure_taxonomy(result),
                "reason": result["failure_reason"],
            }
            for result in stress_results
            if not result["passed"]
        ][:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the stratified 320-task reliability benchmark")
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 19, 42])
    parser.add_argument("--per-scenario", type=int, default=64)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(seeds=args.seeds, per_scenario=args.per_scenario)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
