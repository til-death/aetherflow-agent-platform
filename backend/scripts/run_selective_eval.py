"""Compute raw and selective Tool Router metrics for a frozen case file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.agent.evaluation import _parse_task
from app.agent.tool_registry import (
    TOOLS,
    assess_tool_decision,
    classify_scenario,
    rank_tools,
    task_text,
)
from scripts.run_hard_holdout import _hard_distractors


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    tasks = [_parse_task(item) for item in cases]
    tools = tuple(TOOLS) + tuple(_hard_distractors())
    rows: list[dict[str, Any]] = []
    for task in tasks:
        text = task_text(task)
        scenario, _ = classify_scenario(task, text, tools=tools)
        ranked = rank_tools(text, scenario, tools=tools)
        decision = assess_tool_decision(text, scenario, ranked)
        top1 = ranked[0]["name"] if ranked else None
        raw_correct = top1 == task.expected_tool
        autonomous = decision["decision"] == "execute"
        rows.append(
            {
                "id": task.id,
                "expected_tool": task.expected_tool,
                "actual_tool": top1,
                "raw_top1_correct": raw_correct,
                "decision": decision["decision"],
                "reasons": decision["reasons"],
                "score": ranked[0].get("score", 0.0) if ranked else 0.0,
                "margin": decision["margin"],
                "autonomous_correct": autonomous and raw_correct,
                "unsafe_execution": autonomous and not raw_correct,
            }
        )

    autonomous_rows = [row for row in rows if row["decision"] == "execute"]
    abstained_rows = [row for row in rows if row["decision"] == "abstain"]
    wrong_raw = [row for row in rows if not row["raw_top1_correct"]]
    return {
        "case_count": len(rows),
        "raw_top1_accuracy": _ratio(sum(row["raw_top1_correct"] for row in rows), len(rows)),
        "coverage": _ratio(len(autonomous_rows), len(rows)),
        "selective_accuracy": _ratio(sum(row["autonomous_correct"] for row in rows), len(autonomous_rows)),
        "safe_handling_rate": _ratio(
            sum(row["autonomous_correct"] or row["decision"] == "abstain" for row in rows),
            len(rows),
        ),
        "abstain_count": len(abstained_rows),
        "abstain_rate": _ratio(len(abstained_rows), len(rows)),
        "abstain_precision": _ratio(
            sum(not row["raw_top1_correct"] for row in abstained_rows),
            len(abstained_rows),
        ),
        "unsafe_execution_count": sum(row["unsafe_execution"] for row in rows),
        "unsafe_execution_rate": _ratio(sum(row["unsafe_execution"] for row in rows), len(rows)),
        "unsafe_execution_rate_when_autonomous": _ratio(
            sum(row["unsafe_execution"] for row in rows),
            len(autonomous_rows),
        ),
        "raw_wrong_cases": len(wrong_raw),
        "decision_reasons": _reason_counts(rows),
        "cases": rows,
    }


def _reason_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for reason in row["reasons"]:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute selective Tool Router metrics")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8-sig"))
    report = evaluate_cases(cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
