from __future__ import annotations

from typing import Any

from app.models import WorkflowTask, WorkflowTaskPriority

_SCENARIO_LABELS = {
    "knowledge": "知识检索",
    "workflow": "业务流程",
    "code": "代码任务",
    "analysis": "数据分析",
    "external_api": "外部接口",
    "general": "通用任务",
}
_RISK_LABELS = {"low": "低风险", "medium": "中风险", "high": "高风险"}
_TOOL_LABELS = {
    "hybrid_knowledge_search": "企业知识库检索",
    "graph_neighbor_expand": "关系证据扩展",
    "workflow_state_transition": "流程状态推进",
    "approval_gate": "人工确认关卡",
    "python_sandbox_runner": "Python 沙箱执行",
    "data_frame_profiler": "数据表画像分析",
    "http_api_connector": "HTTP 接口连接器",
    "memory_write_policy": "记忆写入策略",
}


def memory_policy(task: WorkflowTask | Any, critique: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    should_write = critique["confidence"] >= 0.7 and evidence["score"] >= 0.48
    target = (
        "long_term"
        if should_write and task.priority in {WorkflowTaskPriority.HIGH, WorkflowTaskPriority.CRITICAL}
        else "short_term"
    )
    return {
        "decision": f"write={should_write}; target={target}",
        "write": should_write,
        "target": target,
        "importance_score": round((critique["confidence"] + evidence["score"]) / 2, 2),
        "confidence": 0.83 if should_write else 0.68,
    }


def compose_final_answer(
    *,
    scenario: str,
    graph: list[dict[str, Any]],
    evidence: dict[str, Any],
    selected_tool: dict[str, Any],
    tool_result: dict[str, Any],
    critique: dict[str, Any],
) -> str:
    approval = (
        "需要人工确认后才能继续任何修改、发送或对外可见操作。"
        if critique["needs_approval"]
        else "当前结果可以进入执行前确认和 Trace 归档。"
    )
    blockers = "、".join(critique.get("blockers") or ["未发现阻塞项"])
    scenario_label = _SCENARIO_LABELS.get(scenario, scenario)
    risk_label = _RISK_LABELS.get(str(critique["risk_level"]), str(critique["risk_level"]))
    tool_label = _TOOL_LABELS.get(selected_tool["name"], selected_tool.get("label", selected_tool["name"]))
    return "\n".join(
        [
            "处理结论",
            f"场景：{scenario_label}",
            f"选择工具：{tool_label}",
            f"选择理由：{selected_tool.get('description', '')}",
            f"执行结果：{tool_result['summary']}",
            f"证据：{evidence['brief']}",
            f"风险：{risk_label}；阻塞项：{blockers}",
            f"审批：{'需要审批' if critique['needs_approval'] else '无需审批'}；{approval}",
            f"下一步：{'等待人工确认后继续' if critique['needs_approval'] else '确认结果并归档 Trace'}",
            f"运行摘要：DAG {len(graph)} 个节点，置信度 {critique['confidence']:.2f}，证据覆盖率 {critique['evidence_coverage']:.2f}",
        ]
    )
