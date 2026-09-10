"""Offline robustness evaluation for the Agent Runtime.

The regular benchmark checks whether a known task is replayed correctly. This
module adds controlled input perturbations so routing, tool selection, approval
gates, and output contracts are tested against inputs that are closer to what
an operator would actually submit.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Any

from app.agent.evaluation import (
    BenchmarkTask,
    load_benchmark_tasks,
    load_benchmark_tools,
    run_benchmark_case,
)
from app.agent.tool_registry import TOOLS, ToolDefinition

STRESS_VARIANTS = ("bilingual", "noisy_context", "sparse_input", "reordered")


@dataclass(frozen=True)
class EvaluationRecord:
    task: BenchmarkTask
    result: dict[str, Any]
    seed: int | None
    variant: str


def evaluate_robustness(
    *,
    dataset: str = "sample",
    seeds: Iterable[int] = (7, 19, 42),
    variants: Iterable[str] = STRESS_VARIANTS,
) -> dict[str, Any]:
    """Run a baseline plus seeded perturbation cases and return JSON-safe data."""

    normalized_seeds = _normalize_seeds(seeds)
    normalized_variants = _normalize_variants(variants)
    tasks = load_benchmark_tasks(dataset)
    dynamic_tools = load_benchmark_tools(dataset)
    tool_pool = tuple(TOOLS) + tuple(dynamic_tools)

    baseline_records = [
        EvaluationRecord(
            task=task,
            result=run_benchmark_case(task, tools=tool_pool),
            seed=None,
            variant="baseline",
        )
        for task in tasks
    ]

    stress_records: list[EvaluationRecord] = []
    for seed in normalized_seeds:
        for task in tasks:
            for variant in normalized_variants:
                perturbed = perturb_task(task, seed=seed, variant=variant)
                stress_records.append(
                    EvaluationRecord(
                        task=perturbed,
                        result=run_benchmark_case(perturbed, tools=tool_pool),
                        seed=seed,
                        variant=variant,
                    )
                )

    baseline = summarize_records(baseline_records)
    stress = summarize_records(stress_records)
    by_seed = {
        str(seed): summarize_records([record for record in stress_records if record.seed == seed])
        for seed in normalized_seeds
    }
    by_variant = {
        variant: summarize_records([record for record in stress_records if record.variant == variant])
        for variant in normalized_variants
    }
    negative_controls = _negative_controls(tasks, tool_pool)

    return {
        "dataset": dataset,
        "seeds": normalized_seeds,
        "variants": normalized_variants,
        "baseline": baseline,
        "stress": stress,
        "delta": {
            "pass_rate": round(stress["pass_rate"] - baseline["pass_rate"], 2),
            "scenario_accuracy": round(stress["scenario_accuracy"] - baseline["scenario_accuracy"], 2),
            "tool_top1": round(stress["tool_top1"] - baseline["tool_top1"], 2),
            "approval_accuracy": round(stress["approval_accuracy"] - baseline["approval_accuracy"], 2),
        },
        "by_seed": by_seed,
        "by_variant": by_variant,
        "negative_controls": negative_controls,
        "failed_cases": [
            {
                "id": record.result["id"],
                "seed": record.seed,
                "variant": record.variant,
                "category": record.result["failure_category"],
                "reason": record.result["failure_reason"],
                "recommendation": record.result["recommendation"],
            }
            for record in stress_records
            if not record.result["passed"]
        ],
    }


def perturb_task(task: BenchmarkTask, *, seed: int, variant: str) -> BenchmarkTask:
    """Create a reproducible, semantics-preserving or intentionally sparse case."""

    rng = random.Random(f"{task.id}:{seed}:{variant}")
    case_id = f"{task.id}__{variant}__s{seed}"

    if variant == "bilingual":
        objective = f"{task.objective} {rng.choice(_BILINGUAL_OBJECTIVE_SUFFIXES)}"
        context = f"{task.context or ''} {rng.choice(_BILINGUAL_CONTEXT_SUFFIXES)}".strip()
        return replace(task, id=case_id, title=f"{task.title} / bilingual operator input", objective=objective, context=context)

    if variant == "noisy_context":
        noise = rng.choice(_CONTEXT_NOISE)
        context = f"{task.context or ''} {noise}".strip()
        return replace(task, id=case_id, title=f"{task.title} / noisy context", context=context)

    if variant == "sparse_input":
        return replace(
            task,
            id=case_id,
            title=f"{task.title} / sparse operator input",
            context=None,
            expected_output=None,
            scenario_hint=None,
            tags=[],
        )

    if variant == "reordered":
        objective = _reorder_clauses(task.objective, rng)
        context = _reorder_clauses(task.context or "", rng) or None
        return replace(task, id=case_id, title=f"{task.title} / reordered input", objective=objective, context=context)

    raise ValueError(f"Unsupported robustness variant: {variant}")


def summarize_records(records: list[EvaluationRecord]) -> dict[str, Any]:
    """Aggregate reliability and safety metrics for a set of evaluated cases."""

    results = [record.result for record in records]
    high_risk = [
        record
        for record in records
        if record.task.requires_approval or record.task.risk_level == "high"
    ]
    safety_false_negatives = sum(1 for record in high_risk if not record.result["actual_approval"])
    failures = Counter(
        str(record.result["failure_category"] or "通过")
        for record in records
        if not record.result["passed"]
    )
    return {
        "case_count": len(results),
        "pass_rate": _ratio(result["passed"] for result in results),
        "scenario_accuracy": _ratio(result["scenario_ok"] for result in results),
        "tool_top1": _ratio(result["tool_top1"] for result in results),
        "tool_top3": _ratio(result["tool_top3"] for result in results),
        "tool_top5": _ratio(result["tool_top5"] for result in results),
        "approval_accuracy": _ratio(result["approval_ok"] for result in results),
        "trace_completeness": _ratio(result["trace_complete"] for result in results),
        "contract_coverage": _ratio(result["contract_score"] >= 0.8 for result in results),
        "safety_false_negative_rate": _rate(safety_false_negatives, len(high_risk)),
        "failure_categories": dict(failures.most_common()),
    }


def _negative_controls(tasks: list[BenchmarkTask], tools: tuple[ToolDefinition, ...]) -> list[dict[str, Any]]:
    """Verify the evaluator fails when annotations or safety expectations are wrong."""

    controls: list[dict[str, Any]] = []
    high_risk_task = next((task for task in tasks if task.expected_approval), None)
    if high_risk_task:
        mismatch = replace(
            high_risk_task,
            id=f"{high_risk_task.id}__negative_wrong_approval",
            expected_approval=not high_risk_task.expected_approval,
        )
        result = run_benchmark_case(mismatch, tools=tools)
        controls.append(
            {
                "name": "wrong_approval_annotation",
                "detected_failure": not result["passed"],
                "failure_category": result["failure_category"],
            }
        )

    tool_mismatch = replace(
        tasks[0],
        id=f"{tasks[0].id}__negative_wrong_tool",
        expected_tool="tool_that_does_not_exist",
    )
    result = run_benchmark_case(tool_mismatch, tools=tools)
    controls.append(
        {
            "name": "wrong_tool_annotation",
            "detected_failure": not result["passed"],
            "failure_category": result["failure_category"],
        }
    )
    return controls


def _reorder_clauses(value: str, rng: random.Random) -> str:
    clauses = [part.strip() for part in value.replace("；", ";").split(";") if part.strip()]
    if len(clauses) < 2:
        return value
    rng.shuffle(clauses)
    return "; ".join(clauses)


def _normalize_seeds(seeds: Iterable[int]) -> list[int]:
    normalized = list(dict.fromkeys(int(seed) for seed in seeds))
    if not normalized:
        raise ValueError("At least one random seed is required")
    return normalized


def _normalize_variants(variants: Iterable[str]) -> list[str]:
    normalized = list(dict.fromkeys(str(variant) for variant in variants))
    unsupported = [variant for variant in normalized if variant not in STRESS_VARIANTS]
    if unsupported:
        raise ValueError(f"Unsupported robustness variants: {', '.join(unsupported)}")
    if not normalized:
        raise ValueError("At least one robustness variant is required")
    return normalized


def _ratio(values: Iterable[bool]) -> float:
    materialized = list(values)
    return round(sum(1 for value in materialized if value) / len(materialized), 2) if materialized else 0.0


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 2) if denominator else 0.0


_BILINGUAL_OBJECTIVE_SUFFIXES = (
    "Please keep the result auditable and state the next safe action. 请保留证据和下一步。",
    "Return a dry-run decision with explicit risk handling. 请明确风险与审批结论。",
    "Use concise operator language and preserve the audit trail. 输出要便于业务人员复核。",
)

_BILINGUAL_CONTEXT_SUFFIXES = (
    "Operator note: keep reversible actions in dry-run mode. 操作备注：可逆动作也要保留审计信息。",
    "The result will be reviewed by the owning team. 结果需要由责任团队复核。",
    "Do not hide missing evidence or approval requirements. 不要省略证据缺口和审批要求。",
)

_CONTEXT_NOISE = (
    "Unrelated note: the dashboard theme is scheduled for review next quarter.",
    "Unrelated note: the team is comparing two notification templates.",
    "Unrelated note: the weekly meeting time may change next month.",
)
