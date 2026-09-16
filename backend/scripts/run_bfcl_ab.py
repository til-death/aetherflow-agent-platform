"""Run a fixed A/B audit on official BFCL public data.

This script intentionally evaluates only the public multiple and irrelevance
subsets. It compares the lexical ranking path with the current capability-aware
reranker on exactly the same 440 cases. The official BFCL package is supplied
at runtime so the repository does not vendor third-party benchmark data.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from app.agent.tool_registry import ToolDefinition, assess_tool_decision, rank_tools


BFCL_SOURCE = "https://github.com/EnlightenedAI/BFCL"
LEADERBOARD_SOURCE = "https://gorilla.cs.berkeley.edu/leaderboard"
CATEGORIES = ("multiple", "irrelevance")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tokens(value: str) -> tuple[str, ...]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{2,}|[\u4e00-\u9fff]{2,}", value.lower())
    return tuple(dict.fromkeys(words))


def _question_text(case: dict[str, Any]) -> str:
    messages = case.get("question", [])
    return " ".join(
        str(message.get("content", ""))
        for turn in messages
        for message in (turn if isinstance(turn, list) else [turn])
        if isinstance(message, dict) and message.get("role") == "user"
    ).lower()


def _function_tools(case: dict[str, Any], *, capability_aware: bool) -> tuple[ToolDefinition, ...]:
    tools: list[ToolDefinition] = []
    for function in case.get("function", []):
        parameters = function.get("parameters") or {}
        properties = parameters.get("properties") or {}
        required = parameters.get("required") or []
        name = str(function.get("name", "unknown_function"))
        description = str(function.get("description", ""))
        property_text = " ".join(
            f"{key} {value.get('description', '') if isinstance(value, dict) else value}"
            for key, value in properties.items()
        )
        keywords = _tokens(f"{name} {description} {property_text}")
        name_tokens = _tokens(name.replace(".", " ").replace("_", " "))
        required_tokens = _tokens(" ".join(str(item) for item in required))
        capability_cues = tuple(dict.fromkeys((*name_tokens, *required_tokens, *keywords[:6]))) if capability_aware else ()
        tools.append(
            ToolDefinition(
                name=name,
                label=name,
                scenario="general",
                risk_level="low",
                avg_latency_ms=260,
                success_rate=0.75,
                keywords=keywords,
                description=description,
                capability_cues=capability_cues,
                exclusion_cues=(),
            )
        )
    return tuple(tools)


def _expected_function(answer: dict[str, Any]) -> str | None:
    ground_truth = answer.get("ground_truth") or []
    if not ground_truth or not isinstance(ground_truth[0], dict):
        return None
    names = list(ground_truth[0].keys())
    return names[0] if names else None


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _run_category(category: str, data_root: Path) -> list[dict[str, Any]]:
    dataset_path = data_root / f"BFCL_v4_{category}.json"
    answer_path = data_root / "possible_answer" / f"BFCL_v4_{category}.json"
    rows = _load_jsonl(dataset_path)
    answers = {item["id"]: item for item in _load_jsonl(answer_path)} if answer_path.exists() else {}
    results: list[dict[str, Any]] = []
    for case in rows:
        case_id = str(case["id"])
        query = _question_text(case)
        baseline_tools = _function_tools(case, capability_aware=False)
        current_tools = _function_tools(case, capability_aware=True)
        baseline_ranked = rank_tools(query, "general", tools=baseline_tools)
        current_ranked = rank_tools(query, "general", tools=current_tools)
        baseline_top1 = baseline_ranked[0]["name"] if baseline_ranked else None
        current_top1 = current_ranked[0]["name"] if current_ranked else None
        expected = _expected_function(answers.get(case_id, {}))
        baseline_decision = {"decision": "execute", "reasons": []}
        current_decision = assess_tool_decision(query, "general", current_ranked)
        if category == "multiple":
            baseline_correct = baseline_top1 == expected
            # A relevant task succeeds only when the right tool is selected and
            # the policy allows execution; abstaining is safe, but not success.
            current_correct = current_decision["decision"] == "execute" and current_top1 == expected
        else:
            baseline_correct = baseline_top1 is None
            current_correct = current_decision["decision"] == "abstain"
        results.append(
            {
                "id": case_id,
                "category": category,
                "expected_tool": expected,
                "baseline_top1": baseline_top1,
                "current_top1": current_top1,
                "baseline_decision": baseline_decision["decision"],
                "current_decision": current_decision["decision"],
                "current_reasons": current_decision["reasons"],
                "baseline_correct": baseline_correct,
                "current_correct": current_correct,
                "current_score": current_ranked[0]["score"] if current_ranked else 0.0,
                "current_margin": current_decision["margin"],
                "raw_transition": (
                    "wrong_to_correct" if not baseline_correct and current_correct
                    else "correct_to_wrong" if baseline_correct and not current_correct
                    else "correct_to_correct" if baseline_correct and current_correct
                    else "wrong_to_wrong"
                ),
            }
        )
    return results


def _summary(rows: list[dict[str, Any]], category: str) -> dict[str, Any]:
    baseline_correct = sum(row["baseline_correct"] for row in rows)
    current_correct = sum(row["current_correct"] for row in rows)
    transitions = Counter(row["raw_transition"] for row in rows)
    current_autonomous = [row for row in rows if row["current_decision"] == "execute"]
    current_abstained = [row for row in rows if row["current_decision"] == "abstain"]
    return {
        "category": category,
        "case_count": len(rows),
        "baseline_accuracy": _ratio(baseline_correct, len(rows)),
        "current_accuracy": _ratio(current_correct, len(rows)),
        "delta_pp": round((current_correct - baseline_correct) / len(rows) * 100, 2) if rows else 0.0,
        "wrong_to_correct": transitions["wrong_to_correct"],
        "correct_to_wrong": transitions["correct_to_wrong"],
        "coverage": _ratio(len(current_autonomous), len(rows)),
        "selective_accuracy": _ratio(sum(row["current_correct"] for row in current_autonomous), len(current_autonomous)),
        "abstain_rate": _ratio(len(current_abstained), len(rows)),
        "safe_handling_rate": _ratio(sum(row["current_correct"] or row["current_decision"] == "abstain" for row in rows), len(rows)),
        "abstain_reasons": dict(sorted(Counter(reason for row in rows for reason in row["current_reasons"]).items(), key=lambda item: (-item[1], item[0]))),
    }


def run() -> dict[str, Any]:
    import bfcl_eval

    data_root = Path(bfcl_eval.__file__).parent / "data"
    all_rows = [row for category in CATEGORIES for row in _run_category(category, data_root)]
    summaries = {category: _summary([row for row in all_rows if row["category"] == category], category) for category in CATEGORIES}
    baseline_correct = sum(row["baseline_correct"] for row in all_rows)
    current_correct = sum(row["current_correct"] for row in all_rows)
    transitions = Counter(row["raw_transition"] for row in all_rows)
    current_abstained = [row for row in all_rows if row["current_decision"] == "abstain"]
    current_autonomous = [row for row in all_rows if row["current_decision"] == "execute"]
    return {
        "benchmark": "BFCL V4 public data A/B",
        "source": BFCL_SOURCE,
        "leaderboard": LEADERBOARD_SOURCE,
        "bfcl_eval_version": importlib.metadata.version("bfcl-eval"),
        "categories": list(CATEGORIES),
        "evaluation_contract": "Same official function documents and same cases; baseline disables capability cues, current enables capability-aware reranking and abstention.",
        "overall": {
            "case_count": len(all_rows),
            "baseline_accuracy": _ratio(baseline_correct, len(all_rows)),
            "current_accuracy": _ratio(current_correct, len(all_rows)),
            "delta_pp": round((current_correct - baseline_correct) / len(all_rows) * 100, 2) if all_rows else 0.0,
            "wrong_to_correct": transitions["wrong_to_correct"],
            "correct_to_wrong": transitions["correct_to_wrong"],
            "coverage": _ratio(len(current_autonomous), len(all_rows)),
            "selective_accuracy": _ratio(sum(row["current_correct"] for row in current_autonomous), len(current_autonomous)),
            "abstain_rate": _ratio(len(current_abstained), len(all_rows)),
            "safe_handling_rate": _ratio(sum(row["current_correct"] or row["current_decision"] == "abstain" for row in all_rows), len(all_rows)),
        },
        "by_category": summaries,
        "cases": all_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the BFCL V4 public fixed A/B audit")
    parser.add_argument("--output", type=Path, default=Path("docs/evaluation/bfcl_v4_ab/results.json"))
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"overall": report["overall"], "by_category": report["by_category"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
