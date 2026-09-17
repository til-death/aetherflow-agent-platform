from __future__ import annotations

from typing import Any

from app.agent.tool_registry import TOOLS, ToolDefinition

MCP_PROTOCOL_VERSION = "2025-06-18"


def tool_to_mcp(tool: ToolDefinition) -> dict[str, Any]:
    """Map the internal Tool Registry contract to the MCP tools/list shape."""
    return {
        "name": tool.name,
        "title": tool.label,
        "description": tool.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "objective": {"type": "string", "description": "Normalized task objective."},
                "context": {"type": "string", "description": "Optional task context and evidence."},
            },
            "additionalProperties": True,
        },
        "annotations": {
            "readOnlyHint": tool.risk_level == "low",
            "destructiveHint": tool.risk_level == "high",
            "openWorldHint": tool.scenario == "external_api",
        },
        "_aetherflow": {
            "scenario": tool.scenario,
            "riskLevel": tool.risk_level,
            "successRate": tool.success_rate,
            "averageLatencyMs": tool.avg_latency_ms,
            "capabilityCues": list(tool.capability_cues),
            "exclusionCues": list(tool.exclusion_cues),
        },
    }


def build_mcp_tool_catalog(tools: tuple[ToolDefinition, ...] = TOOLS) -> dict[str, Any]:
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "serverInfo": {"name": "shuiliu-runtime", "version": "runtime-v1"},
        "capabilities": {"tools": {"listChanged": False}},
        "tools": [tool_to_mcp(tool) for tool in tools],
    }
