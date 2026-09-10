from __future__ import annotations

import csv
from io import StringIO
from statistics import fmean, stdev
from typing import Any

from app.models import WorkflowTask

_MISSING_VALUES = {"", "na", "n/a", "null", "none", "nan", "missing"}


def execute_tool(
    tool_name: str,
    task: WorkflowTask | Any,
    evidence: dict[str, Any],
    graph: list[dict[str, Any]],
) -> dict[str, Any]:
    if tool_name in {"data_frame_profiler", "toolluban_dataframe_profiler"}:
        return _execute_data_frame_profiler(task, evidence, graph)

    actions = {
        "hybrid_knowledge_search": "已基于混合检索和关联证据生成有依据的回答。",
        "graph_neighbor_expand": "已沿项目、负责人、依赖和事故关系扩展证据链。",
        "workflow_state_transition": "已生成下一流程状态、负责人交接和 SLA 检查点方案。",
        "approval_gate": "已创建高风险流程变更前的人工确认关卡。",
        "python_sandbox_runner": "已生成带资源限制的 Python 沙箱 dry-run 执行报告。",
        "http_api_connector": "已完成接口契约校验，并生成具备幂等键的外部操作方案。",
        "memory_write_policy": "已生成标准化任务摘要和记忆写入建议。",
    }
    expected_output_missing = not task.expected_output
    confidence = max(0.52, evidence["score"] - (0.08 if expected_output_missing else 0.0))
    dynamic_summary = "已生成动态工具 dry-run 方案，包含工具契约、风险处理、证据引用、审批判断和下一步。"
    return {
        "summary": actions.get(tool_name, dynamic_summary),
        "expected_output_missing": expected_output_missing,
        "confidence": round(confidence, 2),
        "evidence_count": len(evidence.get("chunks", [])),
        "graph_node_count": len(graph),
        "dry_run": tool_name in {"python_sandbox_runner", "http_api_connector", "approval_gate"},
        "real_tool": tool_name != "memory_write_policy",
    }


def _execute_data_frame_profiler(
    task: WorkflowTask | Any,
    evidence: dict[str, Any],
    graph: list[dict[str, Any]],
) -> dict[str, Any]:
    profile = profile_csv_payload(_task_payload(task))
    expected_output_missing = not task.expected_output
    if not profile["csv_detected"]:
        confidence = max(0.45, evidence["score"] - 0.18)
        summary = "未检测到可解析的 CSV 内容，因此返回输入契约提醒，没有生成数据画像。"
    else:
        confidence = max(0.72, min(0.96, evidence["score"] + 0.08))
        summary = (
            f"已分析 CSV：{profile['row_count']} 行、{profile['column_count']} 列；"
            f"{profile['columns_with_missing']} 列存在缺失值；"
            f"数值列 {len(profile['numeric_summary'])} 个；"
            f"异常提示 {len(profile['anomaly_hints'])} 条。"
        )

    return {
        "summary": summary,
        "expected_output_missing": expected_output_missing,
        "confidence": round(confidence, 2),
        "evidence_count": len(evidence.get("chunks", [])),
        "graph_node_count": len(graph),
        "dry_run": True,
        "real_tool": True,
        "profile": profile,
    }


def profile_csv_payload(payload: str) -> dict[str, Any]:
    parsed = _extract_best_csv_block(payload)
    if parsed is None:
        return {
            "csv_detected": False,
            "column_count": 0,
            "row_count": 0,
            "missing_values": {},
            "columns_with_missing": 0,
            "numeric_summary": {},
            "categorical_summary": {},
            "anomaly_hints": ["No parseable CSV block found in task context or expected output."],
        }

    headers, rows = parsed
    missing_values = {
        header: sum(1 for row in rows if _is_missing(row.get(header, "")))
        for header in headers
    }
    numeric_summary = _numeric_summary(headers, rows)
    categorical_summary = _categorical_summary(headers, rows, set(numeric_summary))
    anomaly_hints = _anomaly_hints(headers, rows, missing_values, numeric_summary, categorical_summary)

    return {
        "csv_detected": True,
        "column_count": len(headers),
        "row_count": len(rows),
        "missing_values": missing_values,
        "columns_with_missing": sum(1 for count in missing_values.values() if count > 0),
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary,
        "anomaly_hints": anomaly_hints,
    }


def _task_payload(task: WorkflowTask | Any) -> str:
    return "\n\n".join(
        part
        for part in [task.context or "", task.expected_output or "", task.objective or "", task.title or ""]
        if part
    )


def _extract_best_csv_block(payload: str) -> tuple[list[str], list[dict[str, str]]] | None:
    cleaned = payload.replace("```csv", "").replace("```CSV", "").replace("```", "")
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                blocks.append(current)
                current = []
            continue
        if "," in line:
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)

    best: tuple[list[str], list[dict[str, str]]] | None = None
    best_score = 0
    for block in blocks:
        parsed = _parse_csv_block(block)
        if parsed is None:
            continue
        headers, rows = parsed
        score = len(headers) * len(rows)
        if score > best_score:
            best = parsed
            best_score = score
    return best


def _parse_csv_block(lines: list[str]) -> tuple[list[str], list[dict[str, str]]] | None:
    if len(lines) < 2:
        return None
    reader = csv.DictReader(StringIO("\n".join(lines)))
    if not reader.fieldnames:
        return None
    headers = [header.strip() for header in reader.fieldnames if header and header.strip()]
    if len(headers) < 2:
        return None
    rows: list[dict[str, str]] = []
    for row in reader:
        normalized = {header: str(row.get(header, "") or "").strip() for header in headers}
        if any(value for value in normalized.values()):
            rows.append(normalized)
    if not rows:
        return None
    return headers, rows


def _is_missing(value: str | None) -> bool:
    return (value or "").strip().lower() in _MISSING_VALUES


def _to_float(value: str) -> float | None:
    cleaned = value.strip().replace("$", "").replace("%", "")
    if cleaned.lower() in _MISSING_VALUES:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _numeric_summary(headers: list[str], rows: list[dict[str, str]]) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for header in headers:
        non_missing = [row.get(header, "") for row in rows if not _is_missing(row.get(header, ""))]
        values = [_to_float(value) for value in non_missing]
        numeric_values = [value for value in values if value is not None]
        if not non_missing or len(numeric_values) < max(2, int(len(non_missing) * 0.6)):
            continue
        mean = fmean(numeric_values)
        summary[header] = {
            "count": len(numeric_values),
            "min": round(min(numeric_values), 4),
            "max": round(max(numeric_values), 4),
            "mean": round(mean, 4),
            "stdev": round(stdev(numeric_values), 4) if len(numeric_values) > 1 else 0.0,
        }
    return summary


def _categorical_summary(
    headers: list[str],
    rows: list[dict[str, str]],
    numeric_columns: set[str],
) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for header in headers:
        if header in numeric_columns:
            continue
        counts: dict[str, int] = {}
        for row in rows:
            value = row.get(header, "").strip()
            if _is_missing(value):
                continue
            counts[value] = counts.get(value, 0) + 1
        if not counts:
            continue
        top_values = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:5]
        summary[header] = {
            "unique": len(counts),
            "top_values": [{"value": value, "count": count} for value, count in top_values],
        }
    return summary


def _anomaly_hints(
    headers: list[str],
    rows: list[dict[str, str]],
    missing_values: dict[str, int],
    numeric_summary: dict[str, dict[str, float | int]],
    categorical_summary: dict[str, dict[str, Any]],
) -> list[str]:
    hints: list[str] = []
    row_count = len(rows)
    for header, missing_count in missing_values.items():
        if missing_count:
            rate = missing_count / row_count
            severity = "high" if rate >= 0.3 else "low"
            hints.append(f"{header} has {missing_count} missing values ({severity} missingness).")

    for header, summary in numeric_summary.items():
        mean = float(summary["mean"])
        spread = float(summary["stdev"])
        if spread == 0:
            continue
        outliers = []
        for row in rows:
            value = _to_float(row.get(header, ""))
            if value is not None and abs(value - mean) / spread >= 2.5:
                outliers.append(value)
        if outliers:
            hints.append(f"{header} has {len(outliers)} numeric outlier candidate(s).")

    for header, summary in categorical_summary.items():
        top_values = summary.get("top_values", [])
        if top_values and row_count:
            top = top_values[0]
            if top["count"] / row_count >= 0.8:
                hints.append(f"{header} is dominated by '{top['value']}', which may indicate class imbalance.")
        if summary.get("unique", 0) >= max(12, int(row_count * 0.8)):
            hints.append(f"{header} has high cardinality and may be an identifier-like field.")

    duplicate_rows = row_count - len({tuple(row.get(header, "") for header in headers) for row in rows})
    if duplicate_rows:
        hints.append(f"Detected {duplicate_rows} duplicated row(s).")

    return hints or ["No obvious missingness, outlier, duplication, or categorical imbalance hints were detected."]


